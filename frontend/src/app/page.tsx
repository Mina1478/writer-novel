export default function Home() {
  return (
    <div className="flex flex-col flex-1 p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
        <p className="text-zinc-500 mt-2">Welcome to TiniX Story - Advanced AI Novel Generator.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="p-6 rounded-xl border border-border-glass bg-background-card">
          <h3 className="font-semibold text-lg text-brand-secondary mb-2">Recent Projects</h3>
          <p className="text-zinc-400 text-sm">No projects yet. Start by creating a new story!</p>
        </div>
        <div className="p-6 rounded-xl border border-border-glass bg-background-card">
          <h3 className="font-semibold text-lg text-brand-primary mb-2">Capabilities</h3>
          <ul className="text-zinc-400 text-sm space-y-2">
            <li>✨ AI Novel Generation</li>
            <li>🔄 Smart Continue</li>
            <li>📝 Advanced Rewrite</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
