import { useState, useEffect, useRef } from "react";
import Login from "./Login";

const API = "http://34.52.182.216:8080";

const LEVEL_COLORS = {
  CRITICAL: { bg: "#ff000020", border: "#ff0000", text: "#ff4444", icon: "🔴" },
  HIGH:     { bg: "#ff660020", border: "#ff6600", text: "#ff8800", icon: "🟠" },
  MEDIUM:   { bg: "#ffcc0020", border: "#ffcc00", text: "#ffcc00", icon: "🟡" },
  LOW:      { bg: "#00ff0020", border: "#00ff00", text: "#00cc00", icon: "🟢" },
};

function StatCard({ label, value, color, icon }) {
  return (
    <div style={{
      background: "#1a1a2e", border: `1px solid ${color}`,
      borderRadius: 12, padding: "20px", textAlign: "center",
      minWidth: 130, boxShadow: `0 0 15px ${color}40`
    }}>
      <div style={{ fontSize: 28 }}>{icon}</div>
      <div style={{ color, fontSize: 36, fontWeight: "bold" }}>{value}</div>
      <div style={{ color: "#aaa", fontSize: 12, marginTop: 4 }}>{label}</div>
    </div>
  );
}

function AlertRow({ alert, onAnalyze }) {
  const lvl = LEVEL_COLORS[alert.threat_level] || LEVEL_COLORS.LOW;
  const ts  = new Date(alert["@timestamp"]).toLocaleTimeString();
  return (
    <div style={{
      background: lvl.bg, border: `1px solid ${lvl.border}`,
      borderRadius: 8, padding: "10px 14px", marginBottom: 6,
      display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap"
    }}>
      <span style={{ fontSize: 18 }}>{lvl.icon}</span>
      <span style={{ color: "#aaa", fontSize: 11, minWidth: 70 }}>{ts}</span>
      <span style={{ color: lvl.text, fontWeight: "bold", fontSize: 12, minWidth: 80 }}>
        {alert.mitre_technique || "T0000"}
      </span>
      <span style={{ color: "#eee", fontSize: 12, flex: 1 }}>
        {(alert.signature || "").substring(0, 55)}
      </span>
      <span style={{ color: "#aaa", fontSize: 11 }}>{alert.src_ip}</span>
      <span style={{ color: "#4fc3f7", fontSize: 11 }}>
        XGB:{alert.xgb_confidence?.toFixed(0)}%
      </span>
      {alert.lstm_killchain && <span style={{ color: "#f59e0b" }}>⚡KC</span>}
      {alert.vt_score > 0 && (
        <span style={{ color: "#ef4444", fontSize: 11 }}>VT:{alert.vt_score}</span>
      )}
      <button onClick={() => onAnalyze(alert)} style={{
        background: "#2d2d5e", color: "#a78bfa", border: "1px solid #a78bfa",
        borderRadius: 6, padding: "3px 10px", cursor: "pointer", fontSize: 11
      }}>
        🤖 Analyser
      </button>
    </div>
  );
}

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [stats, setStats]         = useState(null);
  const [alerts, setAlerts]       = useState([]);
  const [analysis, setAnalysis]   = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [summary, setSummary]     = useState("");
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("alerts");
  const [minutes, setMinutes]     = useState(10080);
  const chatEndRef = useRef(null);

  // Check if user is logged in on mount
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      setIsLoggedIn(true);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setIsLoggedIn(false);
  };

  const fetchData = async () => {
    const token = localStorage.getItem("token");
    const headers = token ? { "Authorization": `Bearer ${token}` } : {};
    try {
      const [s, a] = await Promise.all([
        fetch(`${API}/api/stats?minutes=${minutes}`, { headers }).then(r => r.json()),
        fetch(`${API}/api/alerts?minutes=${minutes}&size=30`, { headers }).then(r => r.json()),
      ]);
      setStats(s);
      setAlerts(a.alerts || []);
    } catch(e) { console.error(e); }
  };

  useEffect(() => { fetchData(); }, [minutes]);
  useEffect(() => {
    const t = setInterval(fetchData, 15000);
    return () => clearInterval(t);
  }, [minutes]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const handleAnalyze = async (alert) => {
    const token = localStorage.getItem("token");
    setAnalyzing(true);
    setAnalysis("⏳ Analyse Gemini en cours...");
    setActiveTab("analyze");
    try {
      const r = await fetch(`${API}/api/analyze`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ alert })
      });
      const d = await r.json();
      const fmt = typeof d === 'object' && d.threat_level ?
        `🎯 Niveau: ${d.threat_level || 'N/A'} (${Math.round((d.confidence||0)*100)}%)\n` +
        `📍 Phase: ${d.attack_phase || 'N/A'}\n` +
        `🔍 MITRE: ${(d.mitre_techniques||[]).join(', ')}\n\n` +
        `📋 ${d.analysis_summary || ''}\n\n` +
        `✅ Actions Recommandées:\n${(d.recommended_actions||[]).map((a,i)=>`${i+1}. ${a}`).join('\n')}`
        : (typeof d.analysis === 'string' ? d.analysis : JSON.stringify(d, null, 2) || "Erreur");
      setAnalysis(fmt);
    } catch(e) { setAnalysis("❌ Erreur API"); }
    finally { setAnalyzing(false); }
  };

  const handleChat = async () => {
    if (!chatInput.trim()) return;
    const token = localStorage.getItem("token");
    const msg = chatInput;
    setChatInput("");
    setChatHistory(h => [...h, { role: "user", text: msg }]);
    setChatLoading(true);
    try {
      const r = await fetch(`${API}/api/chat`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ message: msg })
      });
      const d = await r.json();
      const chatText = typeof d.response === 'string' ? d.response :
                       d.response ? JSON.stringify(d.response, null, 2) :
                       typeof d === 'string' ? d :
                       JSON.stringify(d, null, 2) || "Erreur";
      setChatHistory(h => [...h, { role: "ai", text: chatText }]);
    } catch(e) {
      setChatHistory(h => [...h, { role: "ai", text: "❌ Erreur API" }]);
    }
    finally { setChatLoading(false); }
  };

  const handleSummary = async () => {
    const token = localStorage.getItem("token");
    setSummaryLoading(true);
    setSummary("⏳ Génération du rapport...");
    setActiveTab("summary");
    try {
      const r = await fetch(`${API}/api/summary`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      const d = await r.json();
      const summaryText = typeof d.summary === 'string' ? d.summary :
                          d.summary ? JSON.stringify(d.summary, null, 2) :
                          typeof d === 'string' ? d :
                          JSON.stringify(d, null, 2) || "Erreur";
      setSummary(summaryText);
    } catch(e) { setSummary("❌ Erreur API"); }
    finally { setSummaryLoading(false); }
  };

  const tabs = [
    { id: "alerts",  label: "🚨 Alertes" },
    { id: "analyze", label: "🤖 Analyse IA" },
    { id: "chat",    label: "💬 Chat SOC" },
    { id: "summary", label: "📋 Rapport" },
  ];

  return isLoggedIn ? (
    <div style={{
      background: "#0a0a1a", minHeight: "100vh", color: "#eee",
      fontFamily: "'Segoe UI', sans-serif", padding: 20
    }}>
      {/* Header */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        marginBottom: 24, borderBottom: "1px solid #2d2d5e", paddingBottom: 16
      }}>
        <div>
          <h1 style={{ margin: 0, color: "#a78bfa", fontSize: 24 }}>
            🛡️ Smart-IDS SOC Dashboard
          </h1>
          <p style={{ margin: "4px 0 0", color: "#888", fontSize: 12 }}>
            XGBoost V3 + Autoencoder + LSTM Kill Chain + Gemini AI
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select value={minutes} onChange={e => setMinutes(+e.target.value)}
            style={{ background: "#1a1a2e", color: "#eee", border: "1px solid #444",
                     borderRadius: 6, padding: "6px 10px", cursor: "pointer" }}>
            <option value={15}>15 min</option>
            <option value={60}>1 heure</option>
            <option value={240}>4 heures</option>
            <option value={480}>8 heures</option>
            <option value={10080}>7 jours</option>
          </select>
          <button onClick={fetchData} style={{
            background: "#2d2d5e", color: "#a78bfa", border: "1px solid #a78bfa",
            borderRadius: 6, padding: "6px 12px", cursor: "pointer", fontSize: 12
          }}>
            🔄 Rafraîchir
          </button>
          <button onClick={handleLogout} style={{
            background: "#ff00001a", color: "#ff4444", border: "1px solid #ff4444",
            borderRadius: 6, padding: "6px 12px", cursor: "pointer", fontSize: 12
          }}>
            🚪 Logout
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
          <StatCard label="Total Alertes" value={stats.total}
            color="#a78bfa" icon="📊" />
          <StatCard label="CRITICAL" value={stats.stats?.CRITICAL || 0}
            color="#ff4444" icon="🔴" />
          <StatCard label="HIGH" value={stats.stats?.HIGH || 0}
            color="#ff8800" icon="🟠" />
          <StatCard label="MEDIUM" value={stats.stats?.MEDIUM || 0}
            color="#ffcc00" icon="🟡" />
          <StatCard label="Kill Chains ⚡" value={stats.kill_chains || 0}
            color="#f59e0b" icon="⚡" />
          <StatCard label="Confiance ML" value={`${stats.avg_confidence?.toFixed(1)}%`}
            color="#4fc3f7" icon="🧠" />
        </div>
      )}

      {/* Top MITRE */}
      {stats?.top_mitre?.length > 0 && (
        <div style={{
          background: "#1a1a2e", borderRadius: 12, padding: 16,
          marginBottom: 20, border: "1px solid #2d2d5e"
        }}>
          <h3 style={{ color: "#a78bfa", margin: "0 0 12px" }}>
            🎯 Top MITRE ATT&CK
          </h3>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {stats.top_mitre.map(([tech, info]) => (
              <div key={tech} style={{
                background: "#2d2d5e", borderRadius: 8, padding: "8px 14px",
                border: "1px solid #4f46e5"
              }}>
                <span style={{ color: "#a78bfa", fontWeight: "bold" }}>{tech}</span>
                <span style={{ color: "#888", fontSize: 11, marginLeft: 8 }}>
                  {info.tactic}
                </span>
                <span style={{ color: "#4fc3f7", marginLeft: 8 }}>
                  ×{info.count}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
            background: activeTab === t.id ? "#2d2d5e" : "#1a1a2e",
            color: activeTab === t.id ? "#a78bfa" : "#888",
            border: `1px solid ${activeTab === t.id ? "#a78bfa" : "#333"}`,
            borderRadius: "8px 8px 0 0", padding: "10px 18px",
            cursor: "pointer", fontSize: 14, fontWeight: activeTab === t.id ? "bold" : "normal"
          }}>{t.label}</button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={{
        background: "#1a1a2e", borderRadius: "0 12px 12px 12px",
        border: "1px solid #2d2d5e", padding: 20, minHeight: 400
      }}>

        {/* Alertes Tab */}
        {activeTab === "alerts" && (
          <div>
            <h3 style={{ color: "#a78bfa", margin: "0 0 16px" }}>
              🚨 Alertes récentes ({alerts.length})
            </h3>
            {alerts.length === 0 ? (
              <p style={{ color: "#888", textAlign: "center", padding: 40 }}>
                💤 Aucune alerte dans la période sélectionnée
              </p>
            ) : (
              alerts.map((a, i) => (
                <AlertRow key={i} alert={a} onAnalyze={handleAnalyze} />
              ))
            )}
          </div>
        )}

        {/* Analyse IA Tab */}
        {activeTab === "analyze" && (
          <div>
            <h3 style={{ color: "#a78bfa", margin: "0 0 16px" }}>
              🤖 Analyse Gemini AI
            </h3>
            {analyzing && (
              <div style={{ color: "#f59e0b", padding: 20, textAlign: "center" }}>
                ⏳ Gemini analyse l'alerte...
              </div>
            )}
            {analysis && !analyzing && (
              <div style={{
                background: "#0f0f2e", border: "1px solid #a78bfa",
                borderRadius: 10, padding: 20,
                whiteSpace: "pre-wrap", lineHeight: 1.7,
                color: "#e0e0e0", fontSize: 14, maxHeight: 500, overflow: "auto"
              }}>
                {analysis}
              </div>
            )}
            {!analysis && !analyzing && (
              <p style={{ color: "#888", textAlign: "center", padding: 40 }}>
                👆 Clique sur "🤖 Analyser" sur une alerte pour obtenir une analyse Gemini
              </p>
            )}
          </div>
        )}

        {/* Chat Tab */}
        {activeTab === "chat" && (
          <div style={{ display: "flex", flexDirection: "column", height: 500 }}>
            <h3 style={{ color: "#a78bfa", margin: "0 0 16px" }}>
              💬 Chat SOC avec Gemini
            </h3>
            <div style={{
              flex: 1, overflowY: "auto", marginBottom: 16,
              background: "#0f0f2e", borderRadius: 10, padding: 16,
              border: "1px solid #2d2d5e"
            }}>
              {chatHistory.length === 0 && (
                <p style={{ color: "#888", textAlign: "center", paddingTop: 40 }}>
                  💬 Posez une question sur les alertes de sécurité...
                  <br/><br/>
                  <span style={{ fontSize: 12 }}>
                    Ex: "Y a-t-il eu des scans de bases de données ?"<br/>
                    "Quelles IPs sont les plus suspectes ?"<br/>
                    "Résume les incidents des 2 dernières heures"
                  </span>
                </p>
              )}
              {chatHistory.map((m, i) => (
                <div key={i} style={{
                  marginBottom: 12,
                  display: "flex",
                  justifyContent: m.role === "user" ? "flex-end" : "flex-start"
                }}>
                  <div style={{
                    maxWidth: "80%", padding: "10px 14px", borderRadius: 10,
                    background: m.role === "user" ? "#2d2d5e" : "#1a3a1a",
                    border: `1px solid ${m.role === "user" ? "#a78bfa" : "#4ade80"}`,
                    color: "#eee", fontSize: 13, lineHeight: 1.6,
                    whiteSpace: "pre-wrap"
                  }}>
                    <span style={{
                      fontSize: 10, color: "#888",
                      display: "block", marginBottom: 4
                    }}>
                      {m.role === "user" ? "👤 Analyste" : "🤖 Gemini"}
                    </span>
                    {typeof m.text === "object" ? JSON.stringify(m.text, null, 2) : m.text}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div style={{ color: "#f59e0b", padding: 10 }}>
                  🤖 Gemini réfléchit...
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <input
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleChat()}
                placeholder="Posez une question sur les alertes..."
                style={{
                  flex: 1, background: "#0f0f2e", color: "#eee",
                  border: "1px solid #444", borderRadius: 8,
                  padding: "10px 14px", fontSize: 13
                }}
              />
              <button onClick={handleChat} disabled={chatLoading} style={{
                background: "#2d2d5e", color: "#a78bfa",
                border: "1px solid #a78bfa", borderRadius: 8,
                padding: "10px 20px", cursor: "pointer", fontSize: 13
              }}>
                Envoyer →
              </button>
            </div>
          </div>
        )}

        {/* Rapport Tab */}
        {activeTab === "summary" && (
          <div>
            <h3 style={{ color: "#a78bfa", margin: "0 0 16px" }}>
              📋 Rapport de Sécurité IA
            </h3>
            <button onClick={handleSummary} disabled={summaryLoading} style={{
              background: "#1a3a1a", color: "#4ade80",
              border: "1px solid #4ade80", borderRadius: 8,
              padding: "10px 20px", cursor: "pointer", marginBottom: 16
            }}>
              {summaryLoading ? "⏳ Génération..." : "🔄 Générer rapport"}
            </button>
            {summary && (
              <div style={{
                background: "#0f0f2e", border: "1px solid #4ade80",
                borderRadius: 10, padding: 20,
                whiteSpace: "pre-wrap", lineHeight: 1.8,
                color: "#e0e0e0", fontSize: 14
              }}>
                {summary}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{
        textAlign: "center", marginTop: 20,
        color: "#555", fontSize: 11
      }}>
        Smart-IDS Framework V4 — XGBoost 98.71% | Autoencoder 99.35% | LSTM Kill Chain | Gemini AI
      </div>
    </div>
  ) : (
    <Login onLoginSuccess={() => setIsLoggedIn(true)} />
  );
}