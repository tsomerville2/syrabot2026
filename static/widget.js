(function () {
  "use strict";

  // --- Configuration ---
  var scriptTag = document.currentScript;
  var clientKey = scriptTag.getAttribute("data-client-key") || "";
  var baseUrl = scriptTag.src.replace(/\/static\/widget\.js(\?.*)?$/, "");

  // Session persistence
  var SESSION_KEY = "starship_chat_session";
  var sessionId =
    sessionStorage.getItem(SESSION_KEY) || crypto.randomUUID();
  sessionStorage.setItem(SESSION_KEY, sessionId);

  // --- Shadow DOM container ---
  var host = document.createElement("div");
  host.id = "starship-chat-widget";
  document.body.appendChild(host);
  var shadow = host.attachShadow({ mode: "open" });

  // --- CSS ---
  var style = document.createElement("style");
  style.textContent =
    '*,:before,:after{box-sizing:border-box;margin:0;padding:0}' +

    /* Bubble */
    '.sc-bubble{position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;' +
    'background:#7c3aed;color:#fff;border:none;cursor:pointer;display:flex;align-items:center;' +
    'justify-content:center;box-shadow:0 4px 14px rgba(124,58,237,.45);z-index:2147483647;transition:transform .2s}' +
    '.sc-bubble:hover{transform:scale(1.08)}' +
    '.sc-bubble svg{width:28px;height:28px;fill:#fff}' +

    /* Window */
    '.sc-window{position:fixed;bottom:92px;right:24px;width:380px;height:520px;border-radius:16px;' +
    'background:#fff;display:flex;flex-direction:column;box-shadow:0 8px 32px rgba(0,0,0,.18);' +
    'z-index:2147483647;overflow:hidden;opacity:0;transform:translateY(20px);' +
    'pointer-events:none;transition:opacity .25s,transform .25s}' +
    '.sc-window.open{opacity:1;transform:translateY(0);pointer-events:auto}' +

    /* Header */
    '.sc-header{background:#7c3aed;color:#fff;padding:14px 16px;display:flex;align-items:center;' +
    'justify-content:space-between;font-family:system-ui,sans-serif;font-size:15px;font-weight:600}' +
    '.sc-close{background:none;border:none;color:#fff;cursor:pointer;font-size:20px;line-height:1;padding:0 2px}' +

    /* Messages area */
    '.sc-messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px;' +
    'font-family:system-ui,sans-serif;font-size:14px;line-height:1.5}' +

    /* Bubbles */
    '.sc-msg{max-width:82%;padding:10px 14px;border-radius:14px;word-wrap:break-word;white-space:pre-wrap}' +
    '.sc-msg.user{align-self:flex-end;background:#7c3aed;color:#fff;border-bottom-right-radius:4px}' +
    '.sc-msg.bot{align-self:flex-start;background:#f3f4f6;color:#1f2937;border-bottom-left-radius:4px}' +

    /* Source link */
    '.sc-source{font-size:12px;color:#7c3aed;margin-top:4px;align-self:flex-start}' +
    '.sc-source a{color:#7c3aed;text-decoration:underline}' +

    /* Typing indicator */
    '.sc-typing{align-self:flex-start;padding:10px 14px;background:#f3f4f6;border-radius:14px;' +
    'border-bottom-left-radius:4px;display:flex;gap:4px;align-items:center}' +
    '.sc-typing span{width:6px;height:6px;background:#9ca3af;border-radius:50%;' +
    'animation:sc-bounce .6s infinite alternate}' +
    '.sc-typing span:nth-child(2){animation-delay:.2s}' +
    '.sc-typing span:nth-child(3){animation-delay:.4s}' +
    '@keyframes sc-bounce{to{opacity:.3;transform:translateY(-4px)}}' +

    /* Input area */
    '.sc-input-row{display:flex;border-top:1px solid #e5e7eb;padding:10px 12px;gap:8px;align-items:center}' +
    '.sc-input{flex:1;border:1px solid #d1d5db;border-radius:20px;padding:8px 14px;font-size:14px;' +
    'font-family:system-ui,sans-serif;outline:none;resize:none;max-height:80px;line-height:1.4}' +
    '.sc-input:focus{border-color:#7c3aed}' +
    '.sc-send{width:36px;height:36px;border-radius:50%;background:#7c3aed;border:none;cursor:pointer;' +
    'display:flex;align-items:center;justify-content:center;flex-shrink:0}' +
    '.sc-send:disabled{opacity:.5;cursor:default}' +
    '.sc-send svg{width:18px;height:18px;fill:#fff}' +

    /* Error */
    '.sc-error{font-size:13px;color:#dc2626;align-self:center;text-align:center;padding:4px 8px}' +

    /* Mobile */
    '@media(max-width:440px){' +
      '.sc-window{right:0;bottom:0;width:100%;height:100%;border-radius:0}' +
      '.sc-bubble{bottom:16px;right:16px}' +
    '}';

  shadow.appendChild(style);

  // --- HTML ---
  var chatIcon = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>';
  var sendIcon = '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';

  // Bubble
  var bubble = document.createElement("button");
  bubble.className = "sc-bubble";
  bubble.innerHTML = chatIcon;
  bubble.setAttribute("aria-label", "Open chat");
  shadow.appendChild(bubble);

  // Window
  var win = document.createElement("div");
  win.className = "sc-window";
  win.innerHTML =
    '<div class="sc-header">' +
      '<span>Chat with us</span>' +
      '<button class="sc-close" aria-label="Close chat">&times;</button>' +
    '</div>' +
    '<div class="sc-messages"></div>' +
    '<div class="sc-input-row">' +
      '<textarea class="sc-input" placeholder="Type a message\u2026" rows="1"></textarea>' +
      '<button class="sc-send" aria-label="Send">' + sendIcon + '</button>' +
    '</div>';
  shadow.appendChild(win);

  // Element refs
  var closeBtn = win.querySelector(".sc-close");
  var messages = win.querySelector(".sc-messages");
  var input = win.querySelector(".sc-input");
  var sendBtn = win.querySelector(".sc-send");

  // --- Toggle ---
  function toggleOpen() {
    var isOpen = win.classList.toggle("open");
    if (isOpen) input.focus();
  }
  bubble.addEventListener("click", toggleOpen);
  closeBtn.addEventListener("click", toggleOpen);

  // --- Auto-resize textarea ---
  input.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 80) + "px";
  });

  // --- Linkify URLs ---
  function linkify(text) {
    return text.replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline">$1</a>'
    );
  }

  // --- Render helpers ---
  function addMessage(text, role) {
    var div = document.createElement("div");
    div.className = "sc-msg " + role;
    if (role === "bot") {
      div.innerHTML = linkify(text);
    } else {
      div.textContent = text;
    }
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  function addSource(url) {
    if (!url) return;
    var div = document.createElement("div");
    div.className = "sc-source";
    div.innerHTML = 'Source: <a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + "</a>";
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function showTyping() {
    var div = document.createElement("div");
    div.className = "sc-typing";
    div.innerHTML = "<span></span><span></span><span></span>";
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  function showError(msg) {
    var div = document.createElement("div");
    div.className = "sc-error";
    div.textContent = msg;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  // --- Send ---
  var sending = false;

  function send() {
    var text = input.value.trim();
    if (!text || sending) return;

    addMessage(text, "user");
    input.value = "";
    input.style.height = "auto";

    sending = true;
    sendBtn.disabled = true;
    var typing = showTyping();

    fetch(baseUrl + "/api/v1/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + clientKey,
      },
      body: JSON.stringify({ question: text, session_id: sessionId }),
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (err) {
            throw new Error(err.detail || "Request failed");
          });
        }
        return res.json();
      })
      .then(function (data) {
        typing.remove();
        addMessage(data.answer, "bot");
        addSource(data.source_url);
      })
      .catch(function (err) {
        typing.remove();
        showError(err.message || "Something went wrong.");
      })
      .finally(function () {
        sending = false;
        sendBtn.disabled = false;
      });
  }

  sendBtn.addEventListener("click", send);
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
})();
