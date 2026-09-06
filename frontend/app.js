const messagesEl = document.getElementById("messages")
const formEl = document.getElementById("chat-form")
const formInputEl = document.getElementById("query")
const sessionIdEl = document.getElementById("session-id")

const newSessionBtn = document.getElementById("new-session-btn");
newSessionBtn.addEventListener("click", newSession);

const clearHistoryBtn = document.getElementById("clear-history-btn");
clearHistoryBtn.addEventListener("click", clearHistory);


function newSessionId() {
    const id = crypto.randomUUID()
    localStorage.setItem("sessionId", id);
    return id
}

function getSessionId(){
    const id = localStorage.getItem("sessionId")
    return id
}

function getChat(){
    const messages = localStorage.getItem("currentChat") || ""
    return messages
}

let sessionId = getSessionId() || newSessionId()
sessionIdEl.textContent = sessionId
let chatHistory = getChat()
messagesEl.innerHTML = chatHistory

function newSession() {
    sessionId = newSessionId()
    sessionIdEl.textContent = sessionId
    messagesEl.innerHTML = ""
    formInputEl.value = ""
    localStorage.setItem("currentChat", "")
}

async function clearHistory() {
    const response = await fetch("/agent/reset-cache", {
        method: "POST" 
    })
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }
    newSession()
}

formEl.addEventListener("submit", async (event) => {
    event.preventDefault()

    const query = formInputEl.value
    messagesEl.innerHTML += `<p> user: ${query} </p>`
    messagesEl.innerHTML += `<div class="loading"><span class="spinner"></span></div>`
    localStorage.setItem("currentChat", messagesEl.innerHTML)

    const response = await fetch(`/agent/${sessionId}/ask`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            query: query
        })
    })

    document.querySelector(".loading")?.remove()

    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }

    const res = await response.text()
    messagesEl.innerHTML += `<p> assistant: ${res} </p>`
    formInputEl.value = ""
    localStorage.setItem("currentChat", messagesEl.innerHTML)
})