/* BERTA Web UI — vanilla JS */

(() => {
  "use strict";

  // ---------- DOM ----------
  const bootScreen   = document.getElementById("boot-screen");
  const app          = document.getElementById("app");
  const chatMessages = document.getElementById("chat-messages");
  const chatInput    = document.getElementById("chat-input");
  const sendBtn      = document.getElementById("send-btn");
  const brainLog     = document.getElementById("brain-log");
  const systemLog    = document.getElementById("system-log");
  const errorsLog    = document.getElementById("errors-log");
  const tasksList    = document.getElementById("tasks-list");
  const connStatus   = document.getElementById("conn-status");
  const connText     = document.getElementById("conn-text");
  const tabs         = document.querySelectorAll(".tab");
  const panels       = document.querySelectorAll(".panel");

  let lastEventId = 0;
  let sse = null;
  let voiceOn = localStorage.getItem("berta_voice") === "1";
  const voiceBtn = document.getElementById("voice-toggle");
  const ttsPlayer = document.getElementById("tts-player");
  let ttsBusy = false;

  function updateVoiceBtn() {
    if (!voiceBtn) return;
    voiceBtn.classList.toggle("on", voiceOn);
    voiceBtn.textContent = voiceOn ? "🔊 ГОЛОС" : "🔇 ГОЛОС";
  }
  updateVoiceBtn();

  if (voiceBtn) {
    voiceBtn.addEventListener("click", () => {
      voiceOn = !voiceOn;
      localStorage.setItem("berta_voice", voiceOn ? "1" : "0");
      updateVoiceBtn();
      if (!voiceOn && ttsPlayer) {
        ttsPlayer.pause();
      }
    });
  }

  async function speakText(text) {
    if (!voiceOn || !text || ttsBusy) return;
    ttsBusy = true;
    if (voiceBtn) voiceBtn.classList.add("loading");
    try {
      const res = await fetch("/api/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
      });
      const data = await res.json();
      if (!res.ok || !data.url) throw new Error(data.error || "TTS failed");
      ttsPlayer.src = data.url;
      await ttsPlayer.play();
    } catch (e) {
      console.warn("TTS:", e);
    } finally {
      ttsBusy = false;
      if (voiceBtn) voiceBtn.classList.remove("loading");
    }
  }


  // ---------- BOOT ----------
  function finishBoot() {
    bootScreen.classList.add("fade-out");
    setTimeout(() => {
      bootScreen.classList.add("hidden");
      app.classList.remove("hidden");
      chatInput.focus();
    }, 650);
  }

  // Минимальное время показа бут-экрана
  setTimeout(finishBoot, 2400);

  // ---------- TABS ----------
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      panels.forEach(p => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById("panel-" + tab.dataset.panel).classList.add("active");

      if (tab.dataset.panel === "tasks") loadTasks();
    });
  });

  // ---------- HELPERS ----------
  function fmtTime(ts) {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function appendChat(role, content) {
    const div = document.createElement("div");
    div.className = "msg " + role;
    div.innerHTML = `
      <div class="role">${role === "user" ? "ВЫ" : "БЕРТА"}</div>
      <div class="text">${escapeHtml(content)}</div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendLog(container, event, extraClass = "") {
    const div = document.createElement("div");
    div.className = "log-entry " + (extraClass || event.type);
    const dataStr = typeof event.data === "object"
      ? JSON.stringify(event.data, null, 2)
      : String(event.data);
    div.innerHTML = `
      <div class="log-time">${fmtTime(event.time)}</div>
      <div class="log-body">[${event.type.toUpperCase()}] ${escapeHtml(dataStr)}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  // ---------- SSE ----------
  function connectSSE() {
    if (sse) sse.close();

    sse = new EventSource("/api/events");

    sse.onopen = () => {
      connStatus.classList.add("online");
      connStatus.classList.remove("offline");
      connText.textContent = "ONLINE";
    };

    sse.onerror = () => {
      connStatus.classList.remove("online");
      connStatus.classList.add("offline");
      connText.textContent = "RECONNECTING…";
      // браузер сам переподключится
    };

    sse.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        handleEvent(event);
      } catch (_) {}
    };
  }

  function handleEvent(event) {
    if (event.id && event.id <= lastEventId) return;
    if (event.id) lastEventId = event.id;

    switch (event.type) {
      case "chat":
        if (event.data.role === "user") {
          // уже показали локально
        } else if (event.data.role === "assistant") {
          const content = event.data.content || "";
          appendChat("assistant", content);
          // озвучка только в Web UI
          if (voiceOn && content) speakText(content);
        }
        break;

      case "brain":
        appendLog(brainLog, event, "brain");
        break;

      case "tool":
      case "system":
      case "task":
      case "status":
        appendLog(systemLog, event);
        break;

      case "error":
        appendLog(errorsLog, event, "error");
        break;
    }
  }

  // ---------- CHAT SEND ----------
  async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    appendChat("user", text);
    chatInput.value = "";
    chatInput.style.height = "auto";

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text })
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
    } catch (err) {
      appendChat("assistant", "[Ошибка связи с агентом: " + err.message + "]");
    }
  }

  sendBtn.addEventListener("click", sendMessage);

  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // авто-высота textarea
  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";
  });

  // ---------- TASKS ----------
  async function loadTasks() {
    try {
      const res = await fetch("/api/tasks");
      const data = await res.json();
      renderTasks(data.tasks || []);
    } catch (_) {
      tasksList.innerHTML = "<div style='color:var(--error)'>Не удалось загрузить задачи</div>";
    }
  }

  function renderTasks(tasks) {
    if (!tasks.length) {
      tasksList.innerHTML = "<div style='color:var(--text-dim)'>Нет задач</div>";
      return;
    }

    tasksList.innerHTML = tasks.map(t => `
      <div class="task-card">
        <div class="task-name">${escapeHtml(t.name)} <span style="color:var(--text-dim);font-size:11px">#${t.id}</span></div>
        <div class="task-status ${t.status}">${t.status.toUpperCase()}</div>
        <div class="task-desc">${escapeHtml(t.description || "")}</div>
      </div>
    `).join("");
  }

  document.getElementById("refresh-tasks").addEventListener("click", loadTasks);

  // ---------- INIT ----------
  // Загружаем историю
  fetch("/api/history")
    .then(r => r.json())
    .then(data => {
      (data.events || []).forEach(handleEvent);
    })
    .catch(() => {})
    .finally(() => {
      connectSSE();
    });

})();
