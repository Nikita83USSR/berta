(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const bootScreen = $("boot-screen");
  const app = $("app");
  const chatMessages = $("chat-messages");
  const chatInput = $("chat-input");
  const sendBtn = $("send-btn");
  const brainLog = $("brain-log");
  const systemLog = $("system-log");
  const errorsLog = $("errors-log");
  const tasksList = $("tasks-list");
  const connStatus = $("conn-status");
  const connText = $("conn-text");
  const agentState = $("agent-state");
  const routeBadge = $("route-badge");
  const voiceBtn = $("voice-toggle");
  const themeToggle = $("theme-toggle");
  const ttsPlayer = $("tts-player");

  let sse = null;
  let lastEventId = 0;
  let voiceOn = localStorage.getItem("berta_voice") !== "0";
  let ttsBusy = false;

  function updateVoiceButton() {
    voiceBtn.classList.toggle("on", voiceOn);
    voiceBtn.textContent = voiceOn ? "🔊 ГОЛОС" : "🔇 ГОЛОС";
  }

  function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("berta_theme", theme);
  }

  function updateState(state) {
    const value = String(state || "idle").toLowerCase();
    agentState.className = "agent-state " + value;
    agentState.textContent = value.toUpperCase();
  }

  function fmtTime(ts) {
    return new Date(ts * 1000).toLocaleTimeString("ru-RU", {
      hour: "2-digit", minute: "2-digit", second: "2-digit"
    });
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function appendChat(role, content, animate = true) {
    const div = document.createElement("article");
    div.className = "msg " + role + (animate ? " message-enter" : "");
    div.innerHTML = `
      <div class="role">${role === "user" ? "ВЫ" : "БЕРТА"}</div>
      <div class="text">${escapeHtml(content)}</div>
    `;
    chatMessages.appendChild(div);
    requestAnimationFrame(() => div.classList.add("message-visible"));
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendLog(container, event, extraClass = "") {
    const div = document.createElement("div");
    div.className = "log-entry " + (extraClass || event.type);
    const data = typeof event.data === "object"
      ? JSON.stringify(event.data, null, 2)
      : String(event.data ?? "");
    div.innerHTML = `
      <div class="log-time">${fmtTime(event.time)}</div>
      <div class="log-body">[${escapeHtml(event.type.toUpperCase())}] ${escapeHtml(data)}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  async function speakText(text) {
    if (!voiceOn || !text || ttsBusy) return;
    ttsBusy = true;
    voiceBtn.classList.add("loading");
    updateState("speaking");
    try {
      const res = await fetch("/api/speak", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text})
      });
      const data = await res.json();
      if (!res.ok || !data.url) throw new Error(data.error || "TTS failed");

      // Ключевой порядок: голос подготовлен -> сообщение уже создаётся только сейчас.
      ttsPlayer.src = data.url;
      await new Promise((resolve, reject) => {
        const onReady = () => { cleanup(); resolve(); };
        const onError = () => { cleanup(); reject(new Error("audio error")); };
        const cleanup = () => {
          ttsPlayer.removeEventListener("canplay", onReady);
          ttsPlayer.removeEventListener("error", onError);
        };
        ttsPlayer.addEventListener("canplay", onReady, {once: true});
        ttsPlayer.addEventListener("error", onError, {once: true});
        ttsPlayer.load();
      });
      appendChat("assistant", text);
      await ttsPlayer.play();
    } catch (err) {
      console.warn("TTS:", err);
      appendChat("assistant", text);
    } finally {
      ttsBusy = false;
      voiceBtn.classList.remove("loading");
      if (agentState.textContent === "SPEAKING") updateState("idle");
    }
  }

  function finishBoot() {
    bootScreen.classList.add("fade-out");
    setTimeout(() => {
      bootScreen.classList.add("hidden");
      app.classList.remove("hidden");
      chatInput.focus();
    }, 550);
  }

  setTheme(localStorage.getItem("berta_theme") || "dark");
  updateVoiceButton();
  setTimeout(finishBoot, 1500);

  voiceBtn.addEventListener("click", () => {
    voiceOn = !voiceOn;
    localStorage.setItem("berta_voice", voiceOn ? "1" : "0");
    updateVoiceButton();
    if (!voiceOn) ttsPlayer.pause();
  });

  themeToggle.addEventListener("click", () => {
    setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
  });

  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
      tab.classList.add("active");
      $("panel-" + tab.dataset.panel).classList.add("active");
      if (tab.dataset.panel === "tasks") loadTasks();
    });
  });

  async function loadTasks() {
    try {
      const res = await fetch("/api/tasks");
      const data = await res.json();
      tasksList.innerHTML = "";
      (data.tasks || []).forEach(task => {
        const card = document.createElement("div");
        card.className = "task-card";
        card.innerHTML = `
          <div class="task-name">${escapeHtml(task.name)}</div>
          <div class="task-status ${escapeHtml(task.status)}">${escapeHtml(task.status.toUpperCase())}</div>
          <div class="task-desc">${escapeHtml(task.description || "")}</div>
        `;
        tasksList.appendChild(card);
      });
      if (!data.tasks?.length) tasksList.innerHTML = '<div class="empty">Нет задач.</div>';
    } catch (e) {
      console.warn(e);
    }
  }

  async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = "";
    chatInput.style.height = "auto";
    appendChat("user", text);
    routeBadge.textContent = "PROCESSING";
    updateState("thinking");
    sendBtn.disabled = true;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({message: text})
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Ошибка отправки");
      }
    } catch (e) {
      appendChat("assistant", "Не удалось отправить запрос: " + e.message);
      updateState("error");
    } finally {
      sendBtn.disabled = false;
      chatInput.focus();
    }
  }

  function unlockAudio() {
    try {
      ttsPlayer.muted = true;
      const p = ttsPlayer.play();
      if (p && p.catch) p.catch(() => {});
      ttsPlayer.pause();
      ttsPlayer.currentTime = 0;
      ttsPlayer.muted = false;
    } catch (_) {}
  }

  sendBtn.addEventListener("click", () => { unlockAudio(); sendMessage(); });
  chatInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
  });
  $("refresh-tasks").addEventListener("click", loadTasks);

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
      updateState("offline");
    };
    sse.onmessage = e => {
      try { handleEvent(JSON.parse(e.data)); } catch (_) {}
    };
  }

  function handleEvent(event) {
    if (event.id && event.id <= lastEventId) return;
    if (event.id) lastEventId = event.id;

    const data = event.data || {};

    if (event.type === "chat") {
      if (data.role === "assistant") {
        if (voiceOn && data.content) {
          // Голосовая ветка сама добавит сообщение в момент готовности аудио.
          speakText(data.content);
        } else {
          appendChat("assistant", data.content || "");
        }
      }
      return;
    }

    if (event.type === "status") {
      updateState(data.state);
      return;
    }

    if (event.type === "router") {
      routeBadge.textContent = data.kind || "ROUTER";
      appendLog(brainLog, event, "router");
      return;
    }

    if (event.type === "brain") {
      appendLog(brainLog, event, "brain");
      return;
    }

    if (event.type === "tool" || event.type === "system") {
      appendLog(systemLog, event, "system");
      return;
    }

    if (event.type === "error") {
      appendLog(errorsLog, event, "error");
      updateState("error");
    }
  }

  connectSSE();
  loadTasks();
})();
