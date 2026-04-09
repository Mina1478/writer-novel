"use client";

import { useState, useEffect } from "react";
import { api } from "@/services/api";

export function TaskSidebar() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    let interval: any;
    if (isOpen) {
      const fetchTasks = async () => {
        try {
          const data = await api.listTasks();
          setTasks(data || []);
        } catch (err) {
          console.error("Error fetching tasks:", err);
        }
      };
      
      fetchTasks();
      interval = setInterval(fetchTasks, 3000);
    }
    return () => clearInterval(interval);
  }, [isOpen]);

  const activeCount = tasks.filter(t => t.status === "running" || t.status === "pending").length;

  return (
    <div className={`fixed bottom-0 right-0 z-50 transition-all duration-300 ${isOpen ? "w-80 h-[500px]" : "w-12 h-12"}`}>
      {/* Toggle Button */}
      {!isOpen ? (
        <button 
          onClick={() => setIsOpen(true)}
          className="w-12 h-12 bg-brand-primary text-black rounded-tl-xl flex items-center justify-center shadow-lg hover:bg-brand-secondary transition-colors relative"
        >
          <span>📋</span>
          {activeCount > 0 && (
            <span className="absolute -top-1 -left-1 w-5 h-5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center animate-bounce">
              {activeCount}
            </span>
          )}
        </button>
      ) : (
        <div className="w-full h-full bg-background-card border-l border-t border-border-glass rounded-tl-2xl shadow-2xl flex flex-col overflow-hidden">
          <div className="p-4 border-b border-border-glass flex justify-between items-center bg-white/5">
            <h3 className="font-bold text-white flex items-center gap-2">
               <span>📋</span> Task Queue
            </h3>
            <button onClick={() => setIsOpen(false)} className="text-zinc-500 hover:text-white">✕</button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {tasks.length === 0 && (
              <p className="text-center text-zinc-500 text-sm mt-10">No recent tasks.</p>
            )}
            
            {tasks.map((task) => (
              <div key={task.id} className="p-3 bg-black/30 border border-border-glass rounded-lg space-y-2">
                <div className="flex justify-between items-start">
                  <div className="text-xs font-semibold text-brand-primary truncate max-w-[150px]">
                    {task.name}
                  </div>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded uppercase font-bold ${
                    task.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                    task.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                    task.status === 'running' ? 'bg-blue-500/20 text-blue-400 animate-pulse' :
                    'bg-zinc-700 text-zinc-400'
                  }`}>
                    {task.status}
                  </span>
                </div>
                
                <div className="text-[11px] text-zinc-400 italic truncate">
                  {task.message}
                </div>

                {(task.status === 'running' || task.status === 'pending') && (
                  <div className="space-y-1">
                    <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                      <div 
                        className="bg-brand-primary h-full transition-all duration-500" 
                        style={{ width: `${task.progress}%` }}
                      ></div>
                    </div>
                    <div className="flex justify-between text-[10px] text-zinc-500">
                       <span>{Math.round(task.progress)}%</span>
                       <button 
                         onClick={() => api.cancelTask(task.id)}
                         className="text-red-400 hover:underline"
                       >
                         Cancel
                       </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
