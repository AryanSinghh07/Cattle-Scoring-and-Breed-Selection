/** Keeps form-like pages (sign-in, account, placeholders) at a comfortable width on PCs. */
export function Narrow({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto flex w-full max-w-xl flex-col gap-4">{children}</div>;
}
