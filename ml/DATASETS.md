# Datasets

Images are never committed to this repo. On Kaggle they are attached as
notebook inputs; locally, keep them outside the project folder.

## Sources

| Dataset | Licence | Images | Breeds | Used for |
|---|---|---|---|---|
| [Indian Bovine breeds](https://www.kaggle.com/datasets/lukex9442/indian-bovine-breeds) (`lukex9442`) | CC0 (public domain) | 5,927 | 41 cattle + buffalo | Breed classifier, detection check |
| [Indian buffalo dataset](https://www.kaggle.com/datasets/atharvadarpude/indian-buffalo-dataset) (`atharvadarpude`) | CC0 (public domain) | 2,785 | 17 buffalo | Breed classifier (more buffalo images), detection check |

Both were collected from Google Images and are **not expert-verified**. The
author of the first dataset says so explicitly.

Rejected candidates:

| Dataset | Reason |
|---|---|
| `atharvadarpude/indian-cattle-image-dataset` (CC0) | Per-breed counts nearly identical to the first dataset; mostly the same images |
| `vedant0dusane/cattle-breed-classification-dataset` (CC BY 4.0) | Missing 9 of our 16 breeds; ~38% synthetic images |
| `sujayroy723/indian-cattle-breeds` | No licence stated |

## Breed names

Only the 16 breeds on the website are used. Folder names are mapped to the
website slugs (`src/data/breeds.ts`), including spelling variants:
`Jaffrabadi` / `Jaffarabadi` → `jafarabadi`, `bhadwari` → `bhadawari`,
`Red_Sindhi` → `red-sindhi`, `Malnad_gidda` → `malnad-gidda`,
`Nili_Ravi` / `nili-ravi` → `nili-ravi`.

## Cleaning (`gopalan_ml/breed_data.py`)

1. Files are opened by their real content, not their extension.
2. Rejected: files under 5 KB (thumbnails), GIFs, images under 64 px,
   unreadable files.
3. Duplicates are found with a 64-bit difference hash (≤ 3 differing bits)
   across **both** datasets:
   - same breed label → keep the largest copy;
   - **different breed labels → drop every copy** (the label can't be trusted).
4. Stratified split per breed: 70% train / 15% validation / 15% test (seed 42),
   done **after** de-duplication so no photo appears in two splits.

| Step | Images |
|---|---|
| Found in our 16 breed folders | 4,284 |
| Rejected (140 tiny files, 16 GIFs) | −156 |
| Duplicate copies removed | −197 |
| Removed for conflicting breed labels | −548 |
| **Kept** | **3,383** |

## Per breed after cleaning

| Breed | Raw (bovine ds) | Raw (buffalo ds) | Kept | Train / Val / Test |
|---|---|---|---|---|
| bhadawari | 86 | 148 | 139 | 97 / 21 / 21 |
| gir | 372 | 0 | 319 | 223 / 48 / 48 |
| hallikar | 186 | 0 | 184 | 128 / 28 / 28 |
| jafarabadi | 102 | 357 | 364 | 254 / 55 / 55 |
| kankrej | 179 | 0 | 176 | 124 / 26 / 26 |
| malnad-gidda | 107 | 0 | 104 | 72 / 16 / 16 |
| mehsana | 95 | 68 | 89 | 63 / 13 / 13 |
| murrah | 173 | 326 | 328 | 230 / 49 / 49 |
| nagpuri | 187 | 156 | 250 | 174 / 38 / 38 |
| nili-ravi | 89 | 189 | 197 | 137 / 30 / 30 |
| ongole | 191 | 0 | 186 | 130 / 28 / 28 |
| rathi | 149 | 0 | 145 | 101 / 22 / 22 |
| red-sindhi | 166 | 0 | 150 | 106 / 22 / 22 |
| sahiwal | 439 | 0 | 409 | 287 / 61 / 61 |
| surti | 64 | 170 | 136 | 96 / 20 / 20 |
| toda | 124 | 161 | 207 | 145 / 31 / 31 |

## Known issues

- **Heavy label noise in the buffalo folders.** The same buffalo photo was
  found filed under up to 7 different breeds, and some "Bhadawari" and
  "Nagpuri" images show cattle, not buffalo. Most conflicting pairs are
  Murrah/Surti, Mehsana/Murrah, Nagpuri/Toda and Bhadawari/Nagpuri. Expect
  lower accuracy on these breeds.
- **Similar-looking cattle breeds:** Gir/Kankrej and Sahiwal/Red Sindhi.
- **Not all images are photos of one animal:** some are text slides,
  infographics, herds or close-ups of the head.
- **Small classes:** Mehsana (89) and Malnad Gidda (104) have the fewest
  images. Training uses class weights to compensate.
- Web photos are not field photos: real phone photos from farms may look
  different, so app accuracy should be re-checked on user photos once
  available.
