import { useEffect, useState } from "react";

export default function App() {
  const [status, setStatus] = useState<string>("…");

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => setStatus(d.status))
      .catch(() => setStatus("backend unreachable"));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: 32 }}>
      <h1>Autocheck — Интеграция 1С</h1>
      <p>Backend: {status}</p>
    </main>
  );
}
