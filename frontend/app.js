const messagesEl = document.getElementById("messages")
const formEl = document.getElementById("chat-form")
const formInputEl = document.getElementById("query")
const sessionIdEl = document.getElementById("session-id")
const sessionEl = document.getElementById("session")
const headerEl = document.getElementById("header")

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

if (messagesEl.innerHTML == ""){
    messagesEl.style.display = "none"
    sessionEl.style.display = "none"
    headerEl.style.display = "block"
} else {
    messagesEl.style.display = "block"
    sessionEl.style.display = "block"
    headerEl.style.display = "none"
}

function newSession() {
    sessionId = newSessionId()
    sessionIdEl.textContent = sessionId
    messagesEl.innerHTML = ""
    formInputEl.value = ""
    localStorage.setItem("currentChat", "")

    messagesEl.style.display = "none"
    sessionEl.style.display = "none"
    headerEl.style.display = "block"
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

async function submitMessage() {
    const query = formInputEl.value
    formInputEl.value = ""

    if (messagesEl.innerHTML == "") {
        messagesEl.innerHTML += `<p id="first-message"> user: ${query} </p>`
    } else {
        messagesEl.innerHTML += `<p class="user-message"> user: ${query} </p>`
    }
    messagesEl.innerHTML += `<div class="loading"><span class="spinner"></span>Thinking ... </div>`
    localStorage.setItem("currentChat", messagesEl.innerHTML)
    messagesEl.style.display = "block"
    sessionEl.style.display = "block"
    headerEl.style.display = "none"

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
    messagesEl.innerHTML += `<p class="assistant-message"> assistant: ${res} </p>`
    localStorage.setItem("currentChat", messagesEl.innerHTML)
}

// formEl.addEventListener("submit", async (event) => {
//     event.preventDefault()
//     submitMessage()
// })


formInputEl.addEventListener("keypress", (event) => {
    if (event.key === 'Enter' && event.shiftKey) {
        return
    }
    else if (event.key === 'Enter') {
        submitMessage()
    }
})