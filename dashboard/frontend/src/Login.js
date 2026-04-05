import { useState } from "react";

export default function Login({ onLoginSuccess }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      console.log("🔐 Login attempt:", { username, password });
      
      const response = await fetch("http://34.52.182.216:8080/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      console.log("📊 Response status:", response.status);
      console.log("📊 Response headers:", {
        contentType: response.headers.get("content-type"),
        corsOrigin: response.headers.get("access-control-allow-origin"),
      });

      if (!response.ok) {
        const errorData = await response.json();
        console.error("❌ HTTP Error:", errorData);
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      console.log("✅ Login successful:", data.user);
      
      localStorage.setItem("token", data.tokens.access_token);
      localStorage.setItem("user", JSON.stringify(data.user));
      onLoginSuccess();
    } catch (err) {
      console.error("🔴 ERROR:", err.message);
      setError(`❌ ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      minHeight: "100vh",
      background: "linear-gradient(135deg, #0f0f1e 0%, #1a1a3e 100%)",
      fontFamily: "Segoe UI, Tahoma, Geneva, Verdana, sans-serif",
    }}>
      <div style={{
        background: "#1a1a2e",
        border: "1px solid #4fc3f7",
        borderRadius: 16,
        padding: "40px",
        maxWidth: 400,
        boxShadow: "0 8px 32px rgba(79, 195, 247, 0.1)",
      }}>
        <h1 style={{ 
          textAlign: "center", 
          color: "#4fc3f7",
          marginBottom: 30,
          fontSize: 28,
        }}>
          🛡️ Smart-IDS
        </h1>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 20 }}>
            <label style={{ color: "#aaa", display: "block", marginBottom: 8 }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={{
                width: "100%",
                padding: "12px",
                background: "#0f0f1e",
                border: "1px solid #4fc3f7",
                borderRadius: 8,
                color: "#fff",
                fontSize: 14,
                boxSizing: "border-box",
              }}
              placeholder="admin"
            />
          </div>

          <div style={{ marginBottom: 30 }}>
            <label style={{ color: "#aaa", display: "block", marginBottom: 8 }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{
                width: "100%",
                padding: "12px",
                background: "#0f0f1e",
                border: "1px solid #4fc3f7",
                borderRadius: 8,
                color: "#fff",
                fontSize: 14,
                boxSizing: "border-box",
              }}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div style={{
              background: "#ff00001a",
              border: "1px solid #ff0000",
              borderRadius: 8,
              padding: 12,
              color: "#ff4444",
              marginBottom: 20,
              fontSize: 12,
              textAlign: "center",
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              padding: "12px",
              background: "#4fc3f7",
              color: "#000",
              border: "none",
              borderRadius: 8,
              fontSize: 14,
              fontWeight: "bold",
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? "⏳ Logging in..." : "🔓 Login"}
          </button>
        </form>

        <div style={{
          marginTop: 30,
          paddingTop: 20,
          borderTop: "1px solid #4fc3f7",
          color: "#aaa",
          fontSize: 12,
          lineHeight: 1.6,
        }}>
          <p style={{ marginBottom: 10 }}>📝 <strong>Demo Credentials:</strong></p>
          
          
          
        </div>
      </div>
    </div>
  );
}
