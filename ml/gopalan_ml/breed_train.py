"""Train, evaluate and export the breed classifier.

Designed to run on a Kaggle GPU via ``ml/notebooks/train_breed_classifier.ipynb``
but works anywhere. Uses ``timm`` (Apache-2.0) to fine-tune a pretrained
ConvNeXt-Tiny on the 16 website breeds.

Outputs (in ``out_dir``):

* ``breed_classifier.onnx``: model for the API (runs with onnxruntime)
* ``labels.json``: class order, preprocessing settings and the "unsure" threshold
* ``metrics.json``: accuracy, per-breed precision/recall, confusion matrix
* ``confusion_matrix.png``, ``training_curves.png``
* ``manifest.csv``: which image went to train/val/test
* ``best.pt``: PyTorch weights (kept out of git)

Local smoke test (CPU, a few minutes)::

    python -m gopalan_ml.breed_train --data-dir <bovine> --data-dir <buffalo> \
        --epochs 1 --limit-per-class 8 --out outputs/breed_smoke
"""

from __future__ import annotations

import argparse
import inspect
import json
import random
import time
import warnings
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset

from .breed_data import BREEDS, Item, prepare, write_manifest

CLASSES = sorted(BREEDS)  # fixed order, saved in labels.json


@dataclass
class TrainConfig:
    model_name: str = "convnext_tiny.fb_in22k_ft_in1k"
    pretrained: bool = True
    image_size: int = 224
    epochs: int = 15
    batch_size: int = 32
    lr: float = 2e-4
    weight_decay: float = 0.05
    label_smoothing: float = 0.1
    num_workers: int = 2
    seed: int = 42
    device: str | None = None
    limit_per_class: int | None = None
    # For the "unsure" threshold. 0.90 made the first model answer only 31% of
    # photos; 0.80 answers ~79% while keeping ~81% of answers correct.
    target_precision: float = 0.80
    out_dir: Path = field(default_factory=lambda: Path("outputs/breed"))


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


class ImageDataset(Dataset):
    def __init__(self, items: list[Item], transform):
        self.items = items
        self.transform = transform
        self.index = {c: i for i, c in enumerate(CLASSES)}

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int):
        it = self.items[i]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # palette/transparency notices
            with Image.open(it.path) as im:
                img = im.convert("RGB")
        return self.transform(img), self.index[it.slug]


def limit_items(items: list[Item], per_class: int | None, seed: int) -> list[Item]:
    """Keep at most ``per_class`` items per breed and split (for quick tests)."""
    if not per_class:
        return items
    rng = random.Random(seed)
    groups: dict[tuple[str, str], list[Item]] = {}
    for it in items:
        groups.setdefault((it.slug, it.split), []).append(it)
    out = []
    for key in sorted(groups):
        g = groups[key]
        n = per_class if key[1] == "train" else max(1, per_class // 2)
        out += rng.sample(g, min(n, len(g)))
    return out


def class_weights(items: list[Item]) -> torch.Tensor:
    """Inverse square-root frequency, normalised to mean 1 (softens imbalance)."""
    counts = Counter(it.slug for it in items)
    w = torch.tensor([1.0 / max(1, counts.get(c, 0)) ** 0.5 for c in CLASSES])
    return w * len(CLASSES) / w.sum()


def make_model(cfg: TrainConfig):
    import timm

    model = timm.create_model(cfg.model_name, pretrained=cfg.pretrained, num_classes=len(CLASSES))
    data_cfg = timm.data.resolve_data_config({"input_size": (3, cfg.image_size, cfg.image_size)}, model=model)
    return model, data_cfg


def make_transforms(data_cfg: dict):
    import timm

    train_tf = timm.data.create_transform(
        **data_cfg, is_training=True, scale=(0.5, 1.0), hflip=0.5, color_jitter=0.2, auto_augment="rand-m7-mstd0.5"
    )
    eval_tf = timm.data.create_transform(**data_cfg)
    return train_tf, eval_tf


@torch.no_grad()
def predict_probs(model, loader, device) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    probs, labels = [], []
    for x, y in loader:
        logits = model(x.to(device, non_blocking=True))
        probs.append(torch.softmax(logits.float(), dim=1).cpu().numpy())
        labels.append(y.numpy())
    return np.concatenate(probs), np.concatenate(labels)


def choose_threshold(probs: np.ndarray, labels: np.ndarray, target_precision: float = 0.9) -> float:
    """Lowest confidence threshold whose accepted predictions reach ``target_precision``."""
    conf = probs.max(axis=1)
    correct = probs.argmax(axis=1) == labels
    for t in np.arange(0.0, 0.96, 0.05):
        accepted = conf >= t
        if accepted.sum() >= max(5, 0.2 * len(labels)) and correct[accepted].mean() >= target_precision:
            return round(float(t), 2)
    return 0.5


def evaluate(probs: np.ndarray, labels: np.ndarray, threshold: float) -> dict:
    from sklearn.metrics import classification_report, confusion_matrix, f1_score

    pred = probs.argmax(axis=1)
    conf = probs.max(axis=1)
    accepted = conf >= threshold
    top3 = np.argsort(-probs, axis=1)[:, :3]
    report = classification_report(
        labels, pred, labels=list(range(len(CLASSES))), target_names=CLASSES, output_dict=True, zero_division=0
    )
    return {
        "images": int(len(labels)),
        "accuracy": round(float((pred == labels).mean()), 4),
        "top3_accuracy": round(float((top3 == labels[:, None]).any(axis=1).mean()), 4),
        "macro_f1": round(float(f1_score(labels, pred, average="macro", zero_division=0)), 4),
        "unsure_threshold": threshold,
        "answered_share": round(float(accepted.mean()), 4),
        "accuracy_when_answered": round(float((pred[accepted] == labels[accepted]).mean()), 4) if accepted.any() else None,
        "per_breed": {
            c: {k: round(float(report[c][k]), 3) for k in ("precision", "recall", "f1-score")} | {"images": int(report[c]["support"])}
            for c in CLASSES
        },
        "confusion_matrix": confusion_matrix(labels, pred, labels=list(range(len(CLASSES)))).tolist(),
        "classes": CLASSES,
    }


def train(items: list[Item], cfg: TrainConfig, log=print):
    """Fine-tune and return (model with best weights, data_cfg, history, device)."""
    set_seed(cfg.seed)
    device = torch.device(cfg.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    model, data_cfg = make_model(cfg)
    model.to(device)
    train_tf, eval_tf = make_transforms(data_cfg)

    train_items = [it for it in items if it.split == "train"]
    val_items = [it for it in items if it.split == "val"]
    pin = device.type == "cuda"
    train_dl = DataLoader(ImageDataset(train_items, train_tf), batch_size=cfg.batch_size, shuffle=True,
                          num_workers=cfg.num_workers, pin_memory=pin, drop_last=len(train_items) > cfg.batch_size)
    val_dl = DataLoader(ImageDataset(val_items, eval_tf), batch_size=cfg.batch_size * 2, num_workers=cfg.num_workers, pin_memory=pin)

    from sklearn.metrics import f1_score

    loss_fn = nn.CrossEntropyLoss(weight=class_weights(train_items).to(device), label_smoothing=cfg.label_smoothing)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    total = max(1, cfg.epochs * len(train_dl))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=cfg.lr, total_steps=total, pct_start=0.1)
    use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    history, best_f1, best_state = [], -1.0, None
    for epoch in range(1, cfg.epochs + 1):
        model.train()
        t0, running, seen = time.time(), 0.0, 0
        for x, y in train_dl:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            with torch.autocast(device_type=device.type, enabled=use_amp):
                loss = loss_fn(model(x), y)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            running += loss.item() * len(y)
            seen += len(y)
        probs, labels = predict_probs(model, val_dl, device)
        val_acc = float((probs.argmax(1) == labels).mean())
        val_f1 = float(f1_score(labels, probs.argmax(1), average="macro", zero_division=0))
        history.append({"epoch": epoch, "train_loss": running / max(1, seen), "val_accuracy": val_acc, "val_macro_f1": val_f1})
        log(f"epoch {epoch}/{cfg.epochs}  loss {running / max(1, seen):.3f}  val acc {val_acc:.3f}  val macro-F1 {val_f1:.3f}  ({time.time() - t0:.0f}s)")
        if val_f1 > best_f1:
            best_f1 = val_f1
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    return model, data_cfg, history, device


def export_onnx(model, path: Path, image_size: int) -> float:
    """Export to ONNX and return the max difference against PyTorch on a random input."""
    import onnxruntime as ort

    model = model.eval().cpu()
    dummy = torch.randn(2, 3, image_size, image_size)
    kwargs = dict(input_names=["image"], output_names=["logits"],
                  dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}}, opset_version=17)
    if "dynamo" in inspect.signature(torch.onnx.export).parameters:
        kwargs["dynamo"] = False  # classic exporter: no extra dependencies, stable output
    torch.onnx.export(model, dummy, str(path), **kwargs)
    with torch.no_grad():
        ref = model(dummy).numpy()
    out = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"]).run(None, {"image": dummy.numpy()})[0]
    return float(np.abs(out - ref).max())


def plot_results(metrics: dict, history: list[dict], out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cm = np.array(metrics["confusion_matrix"], dtype=float)
    norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(10, 9))
    ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(CLASSES)), CLASSES, rotation=60, ha="right")
    ax.set_yticks(range(len(CLASSES)), CLASSES)
    for i in range(len(CLASSES)):
        for j in range(len(CLASSES)):
            if cm[i, j]:
                ax.text(j, i, int(cm[i, j]), ha="center", va="center", fontsize=7, color="white" if norm[i, j] > 0.5 else "black")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(f"Test set: accuracy {metrics['accuracy']:.1%}, macro-F1 {metrics['macro_f1']:.2f}")
    fig.tight_layout()
    fig.savefig(out_dir / "confusion_matrix.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ep = [h["epoch"] for h in history]
    ax.plot(ep, [h["train_loss"] for h in history], label="train loss")
    ax.plot(ep, [h["val_accuracy"] for h in history], label="val accuracy")
    ax.plot(ep, [h["val_macro_f1"] for h in history], label="val macro-F1")
    ax.set_xlabel("epoch")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "training_curves.png", dpi=120)
    plt.close(fig)


def run(roots: list[Path], cfg: TrainConfig, log=print) -> dict:
    """Full pipeline: prepare data -> train -> test -> export. Returns test metrics."""
    out = Path(cfg.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    items, report = prepare([Path(r) for r in roots], seed=cfg.seed)
    items = limit_items(items, cfg.limit_per_class, cfg.seed)
    write_manifest(items, out / "manifest.csv")
    log(f"data: {json.dumps({k: v for k, v in report.to_dict().items() if k != 'per_class'})}")
    log(f"using {len(items)} images: " + json.dumps(Counter(it.split for it in items)))

    model, data_cfg, history, device = train(items, cfg, log)

    _, eval_tf = make_transforms(data_cfg)
    loader = lambda split: DataLoader(ImageDataset([i for i in items if i.split == split], eval_tf),  # noqa: E731
                                      batch_size=cfg.batch_size * 2, num_workers=cfg.num_workers)
    val_probs, val_labels = predict_probs(model, loader("val"), device)
    threshold = choose_threshold(val_probs, val_labels, cfg.target_precision)
    test_probs, test_labels = predict_probs(model, loader("test"), device)
    metrics = evaluate(test_probs, test_labels, threshold)
    metrics["data"] = report.to_dict()
    metrics["history"] = history
    metrics["config"] = {k: (str(v) if isinstance(v, Path) else v) for k, v in asdict(cfg).items()}

    torch.save(model.state_dict(), out / "best.pt")
    metrics["onnx_max_abs_diff"] = export_onnx(model, out / "breed_classifier.onnx", cfg.image_size)
    labels = {
        "classes": CLASSES,
        "names": {c: BREEDS[c][0] for c in CLASSES},
        "types": {c: BREEDS[c][1] for c in CLASSES},
        "model_name": cfg.model_name,
        "input_size": list(data_cfg["input_size"]),
        "mean": list(data_cfg["mean"]),
        "std": list(data_cfg["std"]),
        "crop_pct": data_cfg.get("crop_pct", 0.875),
        "interpolation": data_cfg.get("interpolation", "bicubic"),
        "unsure_threshold": threshold,
    }
    (out / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    plot_results(metrics, history, out)
    log(f"test: accuracy {metrics['accuracy']:.3f}, top-3 {metrics['top3_accuracy']:.3f}, macro-F1 {metrics['macro_f1']:.3f}, "
        f"unsure threshold {threshold} answers {metrics['answered_share']:.0%} with accuracy {metrics['accuracy_when_answered']}")
    return metrics


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Train the breed classifier.")
    ap.add_argument("--data-dir", action="append", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path("outputs/breed"))
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--model", default=TrainConfig.model_name)
    ap.add_argument("--limit-per-class", type=int)
    ap.add_argument("--device")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--no-pretrained", action="store_true")
    a = ap.parse_args(argv)
    cfg = TrainConfig(model_name=a.model, pretrained=not a.no_pretrained, epochs=a.epochs, batch_size=a.batch_size,
                      device=a.device, limit_per_class=a.limit_per_class, num_workers=a.workers, out_dir=a.out)
    run(a.data_dir, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
