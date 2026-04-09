"use client";

import { useState } from "react";
import { api } from "@/services/api";

export default function ToolsPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"rewrite" | "polish">("rewrite");

  const handleProcess = async () => {
    if (!text.trim()) return;
    setLoading(true);
    try {
      if (mode === "rewrite") {
        const res = await fetch('http://127.0.0.1:8000/rewrite', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, style_template: "", use_reflection: false })
        }).then(r => r.json());
        setResult(res.content);
      } else {
        const res = await fetch('http://127.0.0.1:8000/polish', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, polish_type: "general", use_reflection: false })
        }).then(r => r.json());
        setResult(res.content);
      }
    } catch (err) {
      console.error(err);
      setResult("Error processing text.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col flex-1 p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Writing Tools</h1>
        <p className="text-zinc-500 mt-2">Rewrite or polish your content with AI precision.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Input Area */}
        <div className="space-y-4">
          <div className="flex bg-background-card p-1 rounded-lg border border-border-glass w-fit">
            <button
              onClick={() => setMode("rewrite")}
              className={`px-4 py-2 rounded-md text-sm transition-all ${mode === "rewrite" ? "bg-brand-primary text-black font-semibold" : "text-zinc-400 hover:text-white"}`}
            >
              Rewrite
            </button>
            <button
              onClick={() => setMode("polish")}
              className={`px-4 py-2 rounded-md text-sm transition-all ${mode === "polish" ? "bg-brand-primary text-black font-semibold" : "text-zinc-400 hover:text-white"}`}
            >
              Polish
            </button>
          </div>

          <textarea
            className="w-full bg-background-card border border-border-glass rounded-xl p-4 text-sm h-[500px] focus:border-brand-primary outline-none resize-none text-white"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste your content here..."
          />

          <button
            onClick={handleProcess}
            disabled={loading || !text}
            className="w-full py-4 bg-brand-primary text-black font-bold rounded-xl hover:bg-brand-secondary transition-all disabled:opacity-50"
          >
            {loading ? "Processing..." : `Run ${mode === "rewrite" ? "Rewrite" : "Polish"}`}
          </button>
        </div>

        {/* Output Area */}
        <div className="space-y-4">
          <h3 className="font-semibold text-zinc-300">AI Result</h3>
          <div className="w-full bg-black/40 border border-border-glass rounded-xl p-6 text-sm h-[500px] overflow-y-auto text-zinc-300 relative">
             {result ? (
               <div className="whitespace-pre-wrap leading-relaxed">{result}</div>
             ) : (
               <div className="flex items-center justify-center h-full text-zinc-600 italic">
                 Result will be displayed here...
               </div>
             )}
          </div>
          {result && (
             <button 
               onClick={() => { navigator.clipboard.writeText(result); alert("Copied!"); }}
               className="w-full py-2 bg-white/5 border border-border-glass text-zinc-300 rounded-lg hover:bg-white/10 transition-all"
             >
               Copy to Clipboard
             </button>
          )}
        </div>
      </div>
    </div>
  );
}
