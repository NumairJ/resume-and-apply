"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cx } from "@/components/ui";
import { ProviderSwitcher } from "@/components/ProviderSwitcher";

const LINKS = [
  { href: "/apply", label: "Apply" },
  { href: "/applications", label: "Applications" },
  { href: "/settings", label: "Settings" },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="border-b border-rule">
      <div className="mx-auto flex h-14 w-full max-w-5xl items-center gap-8 px-6">
        <Link href="/" className="label-xs text-ink hover:text-muted">
          Resume&nbsp;and&nbsp;Apply
        </Link>

        <nav className="flex items-center gap-6">
          {LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                // The active route is marked with a rule under the word, not a pill or
                // a colour swap — the same hairline vocabulary as the rest of the page.
                className={cx(
                  "border-b-2 py-4 text-sm transition-colors",
                  active
                    ? "border-ink text-ink"
                    : "border-transparent text-muted hover:text-ink",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto">
          <ProviderSwitcher />
        </div>
      </div>
    </header>
  );
}
