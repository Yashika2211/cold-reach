"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useLogout, useMe } from "@/hooks/use-auth";
import { SchedulerControl } from "@/components/scheduler-control";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/campaigns", label: "Campaigns" },
  { href: "/contacts", label: "Contacts" },
  { href: "/companies", label: "Companies" },
  { href: "/resumes", label: "Resumes" },
  { href: "/templates", label: "Templates" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: me } = useMe();
  const logout = useLogout();

  async function handleLogout() {
    await logout.mutateAsync();
    router.push("/login");
  }

  return (
    <nav className="border-b">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-6 py-3">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <span className="font-semibold">ColdReach</span>
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "text-sm text-muted-foreground hover:text-foreground",
                pathname.startsWith(link.href) && "text-foreground font-medium"
              )}
            >
              {link.label}
            </Link>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <SchedulerControl />
          {me?.email}
          <Button variant="outline" size="sm" onClick={handleLogout} disabled={logout.isPending}>
            Log out
          </Button>
        </div>
      </div>
    </nav>
  );
}
