"use client";

import { useState, useEffect } from "react";
import { api } from "@/services/api";

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<any>(null);
  const [backends, setBackends] = useState<any[]>([]);

  useEffect(() => {
    async function loadSettings() {
      try {
        const [cfgData, backendsData] = await Promise.all([
          api.getGenerationConfig(),
          api.getBackends()
        ]);
        setConfig(cfgData);
        setBackends(backendsData);
      } catch (err) {
        console.error("Failed to load settings:", err);
      } finally {
        setLoading(false);
      }
    }
    loadSettings();
  }, []);

  return (
    <div className="flex flex-col flex-1 p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Settings</h1>
        <p className="text-zinc-500 mt-2">Configure API backends and generation parameters.</p>
      </div>

      {loading ? (
        <p className="text-zinc-400 animate-pulse">Loading configuration...</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Backends Section */}
          <div className="p-6 rounded-xl border border-border-glass bg-background-card">
            <h3 className="font-semibold text-lg text-brand-secondary mb-4">API Backends</h3>
            <div className="space-y-4">
              {backends.length === 0 ? (
                <p className="text-sm text-zinc-400">No active backends configured.</p>
              ) : (
                backends.map((b, i) => (
                  <div key={i} className="p-4 bg-black/40 border border-border-glass rounded-md">
                    <div className="flex justify-between items-center mb-2">
                       <h4 className="font-medium text-white">{b.name}</h4>
                       <span className={`px-2 py-1 text-xs rounded-full ${b.enabled ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                         {b.enabled ? "Active" : "Disabled"}
                       </span>
                    </div>
                    <p className="text-xs text-zinc-400">Type: {b.type} | Model: {b.model}</p>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Prompt/Generation Config Section */}
          <div className="p-6 rounded-xl border border-border-glass bg-background-card space-y-6">
            <h3 className="font-semibold text-lg text-brand-primary mb-2">Generation Defaults</h3>
            
            {config && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs text-zinc-400">Temperature</label>
                  <p className="text-sm text-white">{config.temperature}</p>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-zinc-400">Target Words</label>
                  <p className="text-sm text-white">{config.chapter_target_words}</p>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-zinc-400">Writing Style</label>
                  <p className="text-sm text-white">{config.writing_style}</p>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-zinc-400">Tone</label>
                  <p className="text-sm text-white">{config.writing_tone}</p>
                </div>
              </div>
            )}
            
            <p className="text-xs text-zinc-500 mt-4 italic">
              * Frontend editing of configuration is currently pending backend payload schemas.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
