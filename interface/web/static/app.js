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

  function stripForSpeech(text) {
    let t = String(text || "");
    // убрать markdown-разметку и служебные хвосты, чтобы TTS не читал «решётка решётка»
    t = t.replace(/```[\s\S]*?```/g, " ");
    t = t.replace(/`([^`]+)`/g, "$1");
    t = t.replace(/^#{1,6}\s*/gm, "");
    t = t.replace(/\*\*([^*]+)\*\*/g, "$1");
    t = t.replace(/__([^_]+)__/g, "$1");
    t = t.replace(/\*([^*]+)\*/g, "$1");
    t = t.replace(/_([^_]+)_/g, "$1");
    t = t.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
    t = t.replace(/!\[[^\]]*\]\([^)]+\)/g, "");
    t = t.replace(/\[sources?\s*=\s*\[[^\]]*\]\]/gi, "");
    t = t.replace(/\bsources?\s*=\s*\[[^\]]*\]/gi, "");
    t = t.replace(/\bsources?:?\s*[\d,\s\[\]]+/gi, "");
    t = t.replace(/^\s*[-*•]\s+/gm, "");
    t = t.replace(/^\s*\d+\.\s+/gm, "");
    t = t.replace(/https?:\/\/\S+/g, " ");
    t = t.replace(/[#*_~|>]+/g, " ");
    t = t.replace(/\s{2,}/g, " ").trim();
    return t;
  }

  async function speakText(text) {
    if (!voiceOn || !text || ttsBusy) return;
    const spoken = stripForSpeech(text);
    if (!spoken) {
      appendChat("assistant", text);
      return;
    }
    ttsBusy = true;
    voiceBtn.classList.add("loading");
    updateState("speaking");
    try {
      const res = await fetch("/api/speak", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text: spoken})
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
      if (tab.dataset.panel === "brain") loadBrainStats();
    });
  });


  async function loadBrainStats() {
    try {
      const res = await fetch("/api/monitoring");
      if (!res.ok) return;
      const data = await res.json();
      const ai = data.ai || {};
      const set = (id, v) => { const el = $(id); if (el) el.textContent = v; };
      set("stat-ai-total", ai.total ?? "—");
      set("stat-ai-ok", ai.success ?? "—");
      set("stat-ai-err", ai.error ?? "—");
      set("stat-ai-avg", ai.average_response_time != null ? (ai.average_response_time + " с") : "—");
      set("stat-ai-tokens", ((ai.input_tokens || 0) + " / " + (ai.output_tokens || 0)));
      const ev = data.events || {};
      set("stat-events", ev.total_events ?? "—");
      const tts = data.tts || {};
      set("stat-tts", tts.ready ? ("OK · " + (tts.model || "piper")) : "нет");
      const sys = data.system || {};
      set("stat-sys", [sys.berta_version, sys.hostname].filter(Boolean).join(" · ") || "—");
    } catch (e) {
      console.warn("monitoring", e);
    }
  }

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
      if (data.direction === "response" || data.direction === "request") loadBrainStats();
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


  // ========== Voice Input (STT) ==========
  const micBtn = $("mic-btn");
  const voiceStatus = $("voice-status");
  const sttModeEl = $("stt-mode");
  const voiceErrorEl = $("voice-error");
  const vsEnabled = $("vs-enabled");
  const vsAutoSend = $("vs-auto-send");
  const vsLocal = $("vs-local");
  const vsServer = $("vs-server");
  const vsLang = $("vs-lang");
  const vsMaxSec = $("vs-max-sec");

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let voiceRecording = false;
  let recognition = null;
  let mediaRecorder = null;
  let mediaStream = null;
  let audioChunks = [];
  let recordTimer = null;
  let partialText = "";

  function loadVoiceSettings() {
    try {
      const s = JSON.parse(localStorage.getItem("berta_voice_input") || "{}");
      if (vsEnabled) vsEnabled.checked = s.enabled !== false;
      if (vsAutoSend) vsAutoSend.checked = s.autoSend !== false;
      if (vsLocal) vsLocal.checked = s.local !== false;
      if (vsServer) vsServer.checked = !!s.server;
      if (vsLang && s.lang) vsLang.value = s.lang;
      if (vsMaxSec && s.maxSec) vsMaxSec.value = s.maxSec;
    } catch (_) {}
  }
  function saveVoiceSettings() {
    localStorage.setItem("berta_voice_input", JSON.stringify({
      enabled: vsEnabled?.checked !== false,
      autoSend: vsAutoSend?.checked !== false,
      local: vsLocal?.checked !== false,
      server: !!vsServer?.checked,
      lang: vsLang?.value || "ru-RU",
      maxSec: Number(vsMaxSec?.value || 60),
    }));
  }
  loadVoiceSettings();
  ["vs-enabled","vs-auto-send","vs-local","vs-server","vs-lang","vs-max-sec"].forEach(id => {
    const el = $(id);
    if (el) el.addEventListener("change", saveVoiceSettings);
  });

  function setVoiceUI(state, errMsg) {
    // state: ready | listening | recognizing | done
    const labels = {
      ready: "○ Готов",
      listening: "🔴 Слушаю",
      recognizing: "⏳ Распознаю",
      done: "✓ Готово",
    };
    if (voiceStatus) {
      voiceStatus.className = "voice-status " + state;
      voiceStatus.textContent = labels[state] || state;
    }
    if (micBtn) {
      micBtn.classList.toggle("listening", state === "listening");
      micBtn.disabled = vsEnabled && vsEnabled.checked === false;
    }
    if (voiceErrorEl) voiceErrorEl.textContent = errMsg || "";
  }

  function setSttMode(mode) {
    // local | server | external
    if (!sttModeEl) return;
    sttModeEl.className = "stt-mode " + mode;
    sttModeEl.textContent =
      mode === "local" ? "локально (браузер)" :
      mode === "server" ? "через BERTA" :
      "внешний сервис";
  }

  function voiceEnabled() {
    return !vsEnabled || vsEnabled.checked;
  }

  function applyRecognizedText(text, autoSend) {
    text = (text || "").trim();
    if (!text) {
      setVoiceUI("ready", "Пустая команда");
      return;
    }
    chatInput.value = text;
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
    setVoiceUI("done");
    if (autoSend && (!vsAutoSend || vsAutoSend.checked)) {
      unlockAudio();
      sendMessage();
    } else {
      chatInput.focus();
    }
    setTimeout(() => setVoiceUI("ready"), 1200);
  }

  function stopMediaTracks() {
    if (mediaStream) {
      mediaStream.getTracks().forEach(t => t.stop());
      mediaStream = null;
    }
  }

  async function startBrowserSTT() {
    if (!SpeechRecognition) throw new Error("STT_NOT_SUPPORTED");
    if (vsLocal && !vsLocal.checked) throw new Error("LOCAL_STT_DISABLED");
    setSttMode("local");
    partialText = "";
    recognition = new SpeechRecognition();
    recognition.lang = vsLang?.value || "ru-RU";
    recognition.interimResults = true;
    recognition.continuous = true;
    recognition.maxAlternatives = 1;

    return new Promise((resolve, reject) => {
      recognition.onresult = (event) => {
        let interim = "";
        let final = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const t = event.results[i][0].transcript;
          if (event.results[i].isFinal) final += t;
          else interim += t;
        }
        if (final) partialText += final;
        const show = (partialText + " " + interim).trim();
        if (show) chatInput.value = show;
      };
      recognition.onerror = (e) => {
        const map = {
          "not-allowed": "MICROPHONE_DENIED",
          "service-not-allowed": "MICROPHONE_DENIED",
          "audio-capture": "MICROPHONE_NOT_FOUND",
          "network": "NETWORK_ERROR",
          "no-speech": "EMPTY_COMMAND",
          "aborted": "cancelled",
        };
        reject(new Error(map[e.error] || e.error || "STT_ERROR"));
      };
      recognition.onend = () => {
        resolve((partialText || chatInput.value || "").trim());
      };
      try {
        recognition.start();
        setVoiceUI("listening");
      } catch (err) {
        reject(err);
      }
    });
  }

  function stopBrowserSTT() {
    if (recognition) {
      try { recognition.stop(); } catch (_) {}
    }
  }

  async function startMediaRecorder() {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("STT_NOT_SUPPORTED");
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "";
    mediaRecorder = mime ? new MediaRecorder(mediaStream, { mimeType: mime }) : new MediaRecorder(mediaStream);
    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) audioChunks.push(e.data);
    };
    mediaRecorder.start(250);
    setVoiceUI("listening");
  }

  function stopMediaRecorder() {
    return new Promise((resolve) => {
      if (!mediaRecorder || mediaRecorder.state === "inactive") {
        stopMediaTracks();
        resolve(null);
        return;
      }
      mediaRecorder.onstop = () => {
        const type = mediaRecorder.mimeType || "audio/webm";
        const blob = new Blob(audioChunks, { type });
        stopMediaTracks();
        resolve(blob);
      };
      try { mediaRecorder.stop(); } catch (_) { resolve(null); }
    });
  }

  async function serverTranscribe(blob) {
    if (!vsServer || !vsServer.checked) throw new Error("SERVER_STT_DISABLED");
    setSttMode("server");
    setVoiceUI("recognizing");
    const fd = new FormData();
    fd.append("audio", blob, "voice.webm");
    fd.append("language", vsLang?.value || "ru-RU");
    const res = await fetch("/api/voice/transcribe", { method: "POST", body: fd });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "SERVER_STT_ERROR");
    return (data.text || "").trim();
  }

  async function ensureMicPermission() {
    if (!isSecureForMic()) {
      throw new Error("INSECURE_CONTEXT");
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      // На части браузеров SpeechRecognition работает без getUserMedia
      return null;
    }
    // Явный запрос под user gesture (pointerdown) — иначе Android/Chrome сразу not-allowed
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
    return stream;
  }

  async function startRecording() {
    if (voiceRecording || !voiceEnabled()) return;
    voiceRecording = true;
    if (voiceErrorEl) voiceErrorEl.textContent = "";
    unlockAudio();
    const maxMs = Math.max(5, Math.min(120, Number(vsMaxSec?.value || 60))) * 1000;
    clearTimeout(recordTimer);
    recordTimer = setTimeout(() => { stopRecording(true); }, maxMs);

    try {
      if (!isSecureForMic()) throw new Error("INSECURE_CONTEXT");

      // Сначала permission под жестом пользователя
      let permStream = null;
      try {
        permStream = await ensureMicPermission();
      } catch (permErr) {
        const name = permErr && (permErr.name || permErr.message) || "";
        if (/NotAllowed|Permission|Denied/i.test(String(name))) {
          throw new Error("MICROPHONE_DENIED");
        }
        if (/NotFound|DevicesNotFound/i.test(String(name))) {
          throw new Error("MICROPHONE_NOT_FOUND");
        }
        if (String(permErr.message) === "INSECURE_CONTEXT") throw permErr;
        // продолжаем: SpeechRecognition иногда работает и без getUserMedia
      }

      // Priority 1: browser Web Speech API
      if (SpeechRecognition && (!vsLocal || vsLocal.checked)) {
        // останавливаем preview-stream — SpeechRecognition сам откроет mic
        if (permStream) {
          permStream.getTracks().forEach(t => t.stop());
          permStream = null;
        }
        startBrowserSTT().then((text) => {
          if (!voiceRecording) applyRecognizedText(text, true);
        }).catch((err) => {
          if (String(err.message) === "cancelled") return;
          if (vsServer?.checked) {
            startMediaRecorder().catch(e => {
              setVoiceUI("ready", humanVoiceError(e));
              voiceRecording = false;
            });
          } else {
            setVoiceUI("ready", humanVoiceError(err));
            voiceRecording = false;
          }
        });
        return;
      }

      // Priority 3: MediaRecorder → server STT
      if (vsServer?.checked) {
        if (permStream) {
          // переиспользуем уже выданный stream
          mediaStream = permStream;
          audioChunks = [];
          const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : MediaRecorder.isTypeSupported("audio/webm")
              ? "audio/webm"
              : "";
          mediaRecorder = mime
            ? new MediaRecorder(mediaStream, { mimeType: mime })
            : new MediaRecorder(mediaStream);
          mediaRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) audioChunks.push(e.data);
          };
          mediaRecorder.start(250);
          setVoiceUI("listening");
          return;
        }
        await startMediaRecorder();
        return;
      }
      throw new Error("STT_NOT_SUPPORTED");
    } catch (err) {
      voiceRecording = false;
      setVoiceUI("ready", humanVoiceError(err));
    }
  }

  async function stopRecording(fromTimer) {
    if (!voiceRecording && !recognition && !mediaRecorder) return;
    voiceRecording = false;
    clearTimeout(recordTimer);
    setVoiceUI("recognizing");

    // Browser STT path
    if (recognition) {
      stopBrowserSTT();
      // onend will apply text via promise — also apply after short wait
      setTimeout(() => {
        const text = (partialText || chatInput.value || "").trim();
        if (text) applyRecognizedText(text, true);
        else setVoiceUI("ready", fromTimer ? "Лимит записи" : "EMPTY_COMMAND");
        recognition = null;
      }, 400);
      return;
    }

    // MediaRecorder → server
    try {
      const blob = await stopMediaRecorder();
      if (!blob || blob.size < 100) {
        setVoiceUI("ready", "EMPTY_COMMAND");
        return;
      }
      const text = await serverTranscribe(blob);
      applyRecognizedText(text, true);
    } catch (err) {
      setVoiceUI("ready", humanVoiceError(err));
    }
  }

  function cancelRecording() {
    voiceRecording = false;
    clearTimeout(recordTimer);
    stopBrowserSTT();
    recognition = null;
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      try { mediaRecorder.stop(); } catch (_) {}
    }
    stopMediaTracks();
    setVoiceUI("ready");
  }

  function isSecureForMic() {
    // Браузеры разрешают микрофон только в secure context (HTTPS или localhost/127.0.0.1)
    if (window.isSecureContext) return true;
    const h = location.hostname;
    return h === "localhost" || h === "127.0.0.1" || h === "[::1]";
  }

  function humanVoiceError(err) {
    const m = String(err && err.message || err || "");
    if (m === "INSECURE_CONTEXT" || (!isSecureForMic() && (m === "MICROPHONE_DENIED" || m === "not-allowed"))) {
      return (
        "Микрофон заблокирован: страница не в безопасном контексте. " +
        "Откройте UI как https://… или http://localhost:8742 / http://127.0.0.1:8742. " +
        "С телефона по http://192.168.… браузер запрещает микрофон — нужен HTTPS или туннель (например, ssh -L)."
      );
    }
    const map = {
      MICROPHONE_DENIED: "Нет доступа к микрофону. Нажмите 🔒 рядом с адресом → «Микрофон» → Разрешить, обновите страницу.",
      MICROPHONE_NOT_FOUND: "Микрофон не найден. Проверьте, что устройство подключено и не занято другим приложением.",
      STT_NOT_SUPPORTED: "Распознавание речи недоступно. На Android/ПК лучше Chrome. Либо включите «Серверный STT» в настройках.",
      LOCAL_STT_DISABLED: "Локальное STT выключено в настройках.",
      SERVER_STT_DISABLED: "Серверный STT выключен. Включите в настройках голоса.",
      SERVER_STT_ERROR: "Ошибка серверного распознавания.",
      SERVER_STT_NOT_CONFIGURED: "Серверный STT ещё не настроен на BERTA. Используйте Chrome с локальным STT по HTTPS/localhost.",
      NETWORK_ERROR: "Сеть недоступна для распознавания (часто на HTTP). Попробуйте Chrome + localhost/HTTPS.",
      EMPTY_COMMAND: "Речь не распознана. Удерживайте кнопку и говорите громче.",
      cancelled: "",
    };
    return map[m] || m;
  }

  // Push-to-talk: pointer events (mouse + touch)
  if (micBtn) {
    const down = (e) => {
      e.preventDefault();
      startRecording();
    };
    const up = (e) => {
      e.preventDefault();
      stopRecording(false);
    };
    micBtn.addEventListener("pointerdown", down);
    micBtn.addEventListener("pointerup", up);
    micBtn.addEventListener("pointercancel", () => cancelRecording());
    micBtn.addEventListener("pointerleave", (e) => {
      if (voiceRecording && e.pointerType === "mouse") stopRecording(false);
    });
    // prevent context menu on long press
    micBtn.addEventListener("contextmenu", e => e.preventDefault());
  }

  // Desktop hotkey: Ctrl+Space hold
  let hotkeyDown = false;
  window.addEventListener("keydown", (e) => {
    if (e.code === "Space" && e.ctrlKey && !e.repeat && !hotkeyDown) {
      const tag = (e.target && e.target.tagName || "").toLowerCase();
      if (tag === "textarea" || tag === "input") return;
      e.preventDefault();
      hotkeyDown = true;
      startRecording();
    }
    if (e.key === "Escape" && voiceRecording) {
      cancelRecording();
    }
  });
  window.addEventListener("keyup", (e) => {
    if (e.code === "Space" && hotkeyDown) {
      hotkeyDown = false;
      stopRecording(false);
    }
  });

  // Initial STT mode badge + secure context hint
  if (SpeechRecognition) setSttMode("local");
  else if (vsServer?.checked) setSttMode("server");
  else setSttMode("local");
  setVoiceUI("ready");
  if (!isSecureForMic()) {
    setVoiceUI(
      "ready",
      "Внимание: UI открыт не по HTTPS/localhost — микрофон будет заблокирован браузером."
    );
  }

  connectSSE();
  loadTasks();
})();

