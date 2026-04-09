"use client";

import { useState, useEffect } from "react";
import { api } from "@/services/api";

export default function ContinuePage() {
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [project, setProject] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(console.error);
  }, []);

  const handleLoad = async (id: string) => {
    setSelectedId(id);
    setLoading(true);
    try {
      const data = await api.getProject(id);
      setProject(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col flex-1 p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Continue Story</h1>
        <p className="text-zinc-500 mt-2">Resume writing from where you left off.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Project List Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          <h3 className="font-semibold text-zinc-300">Select Project</h3>
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {projects.map((p) => (
              <button
                key={p.id}
                onClick={() => handleLoad(p.id)}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  selectedId === p.id 
                    ? "bg-brand-primary/20 border-brand-primary text-white" 
                    : "bg-background-card border-border-glass text-zinc-400 hover:border-zinc-500"
                }`}
              >
                <div className="font-medium truncate">{p.title}</div>
                <div className="text-xs opacity-60">{p.genre}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Content Area */}
        <div className="lg:col-span-3 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center h-64 text-zinc-500 animate-pulse">
              Loading project data...
            </div>
          ) : project ? (
            <div className="space-y-6">
              <div className="p-6 rounded-xl border border-border-glass bg-background-card">
                <h2 className="text-2xl font-bold text-white mb-4">{project.title}</h2>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div className="p-3 bg-black/30 rounded border border-border-glass">
                    <div className="text-zinc-500 text-xs uppercase mb-1">Chapters</div>
                    <div className="text-white font-semibold">{project.completed_count} / {project.chapters?.length}</div>
                  </div>
                  <div className="p-3 bg-black/30 rounded border border-border-glass">
                    <div className="text-zinc-500 text-xs uppercase mb-1">Total Words</div>
                    <div className="text-white font-semibold">{project.total_words?.toLocaleString()}</div>
                  </div>
                  <div className="p-3 bg-black/30 rounded border border-border-glass">
                    <div className="text-zinc-500 text-xs uppercase mb-1">Last Updated</div>
                    <div className="text-white font-semibold">{new Date(project.updated_at).toLocaleDateString()}</div>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-zinc-200">Chapter List</h3>
                <div className="space-y-2">
                  {project.chapters?.map((ch: any) => (
                    <div key={ch.num} className="p-4 bg-background-card border border-border-glass rounded-lg flex items-center justify-between group hover:border-brand-primary/50 transition-colors">
                      <div>
                        <span className="text-zinc-500 mr-2">#{ch.num}</span>
                        <span className="text-white font-medium">{ch.title}</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-xs text-zinc-500">{ch.word_count || 0} words</span>
                        <button 
                          onClick={async () => {
                            try {
                              await api.startBulkGen({ project_id: selectedId, chapter_nums: [ch.num] });
                              alert("Generation task started. Check the Task Sidebar!");
                            } catch (err) {
                              alert("Failed to start task");
                            }
                          }}
                          className="px-4 py-1.5 bg-brand-primary/10 text-brand-primary border border-brand-primary/30 rounded hover:bg-brand-primary hover:text-black transition-all"
                        >
                          {ch.content ? "Rewrite" : "Write"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-96 border-2 border-dashed border-border-glass rounded-2xl text-zinc-600">
              <p>Please select a project from the sidebar to continue writing.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
