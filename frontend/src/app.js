;(function () {
  const WEBSOCKET_URL = window.CHAT_CONFIG.websocketUrl

  const conversations = []
  let activeId = null
  let socket = null
  let liveRow = null
  let liveKind = null

  const messagesEl = document.getElementById('messages')
  const listEl = document.getElementById('conversation-list')
  const bannerEl = document.getElementById('connection-banner')
  const form = document.getElementById('composer')
  const input = document.getElementById('prompt-input')

  function newConversation() {
    const conversation = {
      id: crypto.randomUUID(),
      sessionId: crypto.randomUUID(),
      messages: [],
      status: 'idle',
      pendingText: '',
      revealed: '',
    }
    conversations.push(conversation)
    activeId = conversation.id
    render()
  }

  function findConversation(id) {
    return conversations.find((conversation) => conversation.id === id)
  }

  function findConversationBySessionId(sessionId) {
    return conversations.find(
      (conversation) => conversation.sessionId === sessionId
    )
  }

  function render() {
    renderSidebar()
    renderMessages()
  }

  function renderSidebar() {
    listEl.innerHTML = ''
    conversations.forEach((conversation, index) => {
      const item = document.createElement('li')
      item.textContent = `Conversación ${index + 1}`
      if (conversation.id === activeId) {
        item.classList.add('active')
      }
      item.addEventListener('click', () => {
        activeId = conversation.id
        render()
      })
      listEl.appendChild(item)
    })
  }

  function renderMessages() {
    liveRow = null
    liveKind = null
    const conversation = findConversation(activeId)
    messagesEl.innerHTML = ''
    if (!conversation) {
      return
    }
    conversation.messages.forEach((message) => {
      messagesEl.appendChild(bubble(message.role, message.text))
    })
    if (conversation.status === 'tool') {
      setLive(typingIndicator('Consultando datos...'), 'dots')
    } else if (
      conversation.status === 'typing' &&
      conversation.revealed === ''
    ) {
      setLive(typingIndicator(), 'dots')
    } else if (conversation.revealed !== '') {
      setLive(bubble('assistant', conversation.revealed), 'text')
    }
    input.disabled = conversation.status !== 'idle'
    scrollToBottom()
  }

  function updateLive(conversation) {
    if (conversation.id !== activeId) {
      return
    }
    if (conversation.status === 'tool') {
      if (liveKind !== 'dots') {
        setLive(typingIndicator('Consultando datos...'), 'dots')
      }
    } else if (conversation.revealed === '') {
      if (liveKind !== 'dots') {
        setLive(typingIndicator(), 'dots')
      }
    } else if (liveKind !== 'text') {
      setLive(bubble('assistant', conversation.revealed), 'text')
    } else {
      liveRow.querySelector('.bubble').innerHTML = formatText(
        conversation.revealed
      )
    }
    input.disabled = conversation.status !== 'idle'
    scrollToBottom()
  }

  const REVEAL_INTERVAL_MS = 20
  const REVEAL_MIN_CHARS = 2
  const REVEAL_CATCHUP_TICKS = 20
  let revealTimer = null

  function revealStep(conversation) {
    const remaining =
      conversation.pendingText.length - conversation.revealed.length
    if (remaining <= 0) {
      return false
    }
    const step = Math.max(
      REVEAL_MIN_CHARS,
      Math.ceil(remaining / REVEAL_CATCHUP_TICKS)
    )
    conversation.revealed = conversation.pendingText.slice(
      0,
      conversation.revealed.length + step
    )
    return true
  }

  function tickReveal() {
    let activeAdvanced = false
    conversations.forEach((conversation) => {
      if (revealStep(conversation) && conversation.id === activeId) {
        activeAdvanced = true
      }
    })
    if (activeAdvanced) {
      updateLive(findConversation(activeId))
    }
    const stillRevealing = conversations.some(
      (conversation) =>
        conversation.revealed.length < conversation.pendingText.length
    )
    if (!stillRevealing) {
      clearInterval(revealTimer)
      revealTimer = null
    }
  }

  function ensureRevealTimer() {
    if (revealTimer === null) {
      revealTimer = setInterval(tickReveal, REVEAL_INTERVAL_MS)
    }
  }

  function setLive(rowEl, kind) {
    if (liveRow) {
      liveRow.remove()
    }
    liveRow = rowEl
    liveKind = kind
    messagesEl.appendChild(rowEl)
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight
  }

  const AVATARS = { user: '🧑', assistant: '🤖', status: '🤖' }

  function row(role, contentEl) {
    const wrapper = document.createElement('div')
    wrapper.className = `row ${role}`
    const avatar = document.createElement('div')
    avatar.className = `avatar ${role}`
    avatar.textContent = AVATARS[role]
    wrapper.appendChild(avatar)
    wrapper.appendChild(contentEl)
    return wrapper
  }

  function bubble(role, text) {
    const div = document.createElement('div')
    div.className = `bubble ${role}`
    if (role === 'assistant') {
      div.innerHTML = formatText(text)
    } else {
      div.textContent = text
    }
    return row(role, div)
  }

  function escapeHtml(text) {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
  }

  function formatText(text) {
    return escapeHtml(text)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>')
  }

  function typingIndicator(label) {
    const div = document.createElement('div')
    div.className = 'bubble status'
    const dots = document.createElement('span')
    dots.className = 'dots'
    dots.append(
      document.createElement('span'),
      document.createElement('span'),
      document.createElement('span')
    )
    div.appendChild(dots)
    if (label) {
      const text = document.createElement('span')
      text.textContent = label
      div.appendChild(text)
    }
    return row('status', div)
  }

  function ensureSocket() {
    if (socket && socket.readyState === WebSocket.OPEN) {
      return Promise.resolve(socket)
    }
    return new Promise((resolve, reject) => {
      socket = new WebSocket(WEBSOCKET_URL)
      socket.addEventListener('open', () => resolve(socket))
      socket.addEventListener('message', onMessage)
      socket.addEventListener('close', onDisconnect)
      socket.addEventListener('error', () =>
        reject(new Error('websocket error'))
      )
    })
  }

  function onDisconnect() {
    bannerEl.hidden = false
  }

  function onMessage(event) {
    const payload = JSON.parse(event.data)
    const conversation = findConversationBySessionId(payload.sessionId)
    if (!conversation) {
      return
    }
    if (payload.type === 'tool_start') {
      conversation.status = 'tool'
    } else if (payload.type === 'delta') {
      conversation.status = 'typing'
      conversation.pendingText += payload.text
      ensureRevealTimer()
    } else if (payload.type === 'done') {
      if (conversation.pendingText !== '') {
        conversation.messages.push({
          role: 'assistant',
          text: conversation.pendingText,
        })
      }
      conversation.pendingText = ''
      conversation.revealed = ''
      conversation.status = 'idle'
    }
    if (conversation.id !== activeId) {
      return
    }
    if (payload.type === 'done') {
      renderMessages()
    } else {
      updateLive(conversation)
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault()
    const text = input.value.trim()
    const conversation = findConversation(activeId)
    if (text === '' || !conversation || conversation.status !== 'idle') {
      return
    }
    conversation.messages.push({ role: 'user', text })
    conversation.status = 'typing'
    conversation.pendingText = ''
    conversation.revealed = ''
    input.value = ''
    renderMessages()

    const ws = await ensureSocket()
    ws.send(
      JSON.stringify({
        action: 'sendMessage',
        sessionId: conversation.sessionId,
        prompt: text,
      })
    )
  })

  document
    .getElementById('new-conversation')
    .addEventListener('click', newConversation)

  newConversation()
})()
