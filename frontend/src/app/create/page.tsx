"use client";

import { useState, useEffect } from "react";
import { api } from "@/services/api";

export default function CreatePage() {
  const [genres, setGenres] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    title: "",
    genre: "",
    character_setting: "",
    world_setting: "",
    plot_idea: "",
    total_chapters: 20
  });
  const [outline, setOutline] = useState<string>("");
  const [statusMsg, setStatusMsg] = useState<string>("");

  useEffect(() => {
    // Fetch genres on mount
    api.getGenres().then((data) => {
      setGenres(data || []);
      if (data && data.length > 0) {
        setFormData((prev) => ({ ...prev, genre: data[0].name }));
      }
    }).catch(err => {
      console.error("Error fetching genres:", err);
    });
  }, []);

  const handleGenerateOutline = async () => {
    try {
      setLoading(true);
      setStatusMsg("Generating outline. Please wait...");
      setOutline("");
      
      const res = await api.generateOutline({
        title: formData.title,
        genre: formData.genre,
        sub_genres: [],
        total_chapters: formData.total_chapters,
        character_setting: formData.character_setting,
        world_setting: formData.world_setting,
        plot_idea: formData.plot_idea
      });
      
      setOutline(res.content || "");
      setStatusMsg(res.message || "Success");
    } catch (err: any) {
      setStatusMsg("Error: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col flex-1 p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Create Story</h1>
        <p className="text-zinc-500 mt-2">Design your novel settings and generate an outline.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Form Column */}
        <div className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">Novel Title</label>
            <input 
              className="w-full bg-background-card border border-border-glass rounded-md p-2 text-sm focus:border-brand-primary outline-none text-white"
              value={formData.title}
              onChange={(e) => setFormData({...formData, title: e.target.value})}
              placeholder="Enter your novel title..."
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">Genre</label>
            <select 
              className="w-full bg-background-card border border-border-glass rounded-md p-2 text-sm focus:border-brand-primary outline-none text-white"
              value={formData.genre}
              onChange={(e) => setFormData({...formData, genre: e.target.value})}
            >
              {genres.map(g => (
                <option key={g.name} value={g.name}>{g.name}</option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">Character Settings</label>
            <textarea 
              className="w-full bg-background-card border border-border-glass rounded-md p-2 text-sm min-h-[100px] focus:border-brand-primary outline-none text-white"
              value={formData.character_setting}
              onChange={(e) => setFormData({...formData, character_setting: e.target.value})}
              placeholder="Describe main characters, personalities..."
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">World Setting</label>
            <textarea 
              className="w-full bg-background-card border border-border-glass rounded-md p-2 text-sm min-h-[100px] focus:border-brand-primary outline-none text-white"
              value={formData.world_setting}
              onChange={(e) => setFormData({...formData, world_setting: e.target.value})}
              placeholder="Describe the world, magic system, laws..."
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">Plot Idea</label>
            <textarea 
              className="w-full bg-background-card border border-border-glass rounded-md p-2 text-sm min-h-[100px] focus:border-brand-primary outline-none text-white"
              value={formData.plot_idea}
              onChange={(e) => setFormData({...formData, plot_idea: e.target.value})}
              placeholder="Main conflict, goals, and ending idea..."
            />
          </div>

          <button 
            disabled={loading || !formData.title || !formData.genre}
            onClick={handleGenerateOutline}
            className="w-full py-3 bg-brand-primary text-black font-semibold rounded-md hover:bg-brand-secondary transition-colors disabled:opacity-50"
          >
            {loading ? "Generating..." : "Generate Outline"}
          </button>
        </div>

        {/* Outline / Results Column */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-foreground">Generated Outline</h2>
          
          {statusMsg && (
            <div className="p-3 bg-blue-900/30 border border-blue-500/30 text-blue-300 rounded-md text-sm">
              {statusMsg}
            </div>
          )}

          <textarea 
            className="w-full bg-black/40 border border-border-glass rounded-md p-4 text-sm h-[600px] font-mono text-zinc-300 focus:border-brand-primary outline-none resize-none"
            value={outline}
            readOnly
            placeholder="Your generated outline will appear here..."
          />
        </div>
      </div>
    </div>
  );
}
