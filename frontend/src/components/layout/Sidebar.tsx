import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  { name: "Dashboard", href: "/" },
  { name: "Create New", href: "/create" },
  { name: "Continue Story", href: "/continue" },
  { name: "Writing Tools", href: "/tools" },
  { name: "Settings", href: "/settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex flex-col w-64 bg-background-card border-r border-border-glass h-screen sticky top-0">
      <div className="flex items-center justify-center h-20 border-b border-border-glass">
        <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-brand-primary to-brand-secondary">
          TiniX Story
        </h1>
      </div>
      <nav className="flex-1 px-4 py-6 space-y-2">
        {navigation.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-all duration-200 ${
                isActive
                  ? "bg-brand-primary/20 text-brand-secondary border border-brand-primary/30"
                  : "text-zinc-400 hover:bg-white/5 hover:text-white"
              }`}
            >
              {item.name}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-border-glass text-xs text-zinc-500 text-center">
        TiniX Story v1.0
      </div>
    </div>
  );
}
