"use client";

import { useEffect, useState } from "react";
import styles from "./page.module.css";

export default function Home() {
  const [status, setStatus] = useState({ state: "loading" });

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;

    fetch(apiUrl)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed with status ${res.status}`);
        return res.json();
      })
      .then((data) => setStatus({ state: "ok", message: data.message }))
      .catch(() => setStatus({ state: "error" }));
  }, []);

  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <div className={styles.intro}>
          <h1>Resume and Apply</h1>
          {status.state === "loading" && <p>Checking backend status…</p>}
          {status.state === "ok" && <p>✅ {status.message}</p>}
          {status.state === "error" && (
            <p>⚠️ Could not reach the backend. Is it running?</p>
          )}
        </div>
      </main>
    </div>
  );
}
