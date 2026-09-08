import { renderData } from "./rendering.js"

const messagesEl = document.getElementById("messages")
const messagesWrapperEl = document.getElementById("messages-wrapper")
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

const isFetching = localStorage.getItem("isFetching") === "true"
clearHistoryBtn.disabled = isFetching

if (messagesEl.innerHTML == ""){
    messagesWrapperEl.style.display = "none"
    sessionEl.style.display = "none"
    headerEl.style.display = "block"
} else {
    messagesWrapperEl.style.display = "block"
    sessionEl.style.display = "block"
    headerEl.style.display = "none"
}

function setFetching(isFetching) {
    localStorage.setItem("isFetching", isFetching)
    clearHistoryBtn.disabled = isFetching
}

function newSession() {
    // in case fetching throws error, we can re-enable the clear history button by starting a new session
    setFetching(false)

    sessionId = newSessionId()
    sessionIdEl.textContent = sessionId
    messagesEl.innerHTML = ""
    formInputEl.value = ""
    localStorage.setItem("currentChat", "")

    messagesWrapperEl.style.display = "none"
    sessionEl.style.display = "none"
    headerEl.style.display = "block"
}

async function clearHistory() {
    newSession()
    const response = await fetch("/agent/reset-cache", {
        method: "POST" 
    })
    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }
}

async function submitMessage() {
    const query = formInputEl.value
    formInputEl.value = ""

    //disallow clear history while fetching data
    setFetching(true)

    if (messagesEl.innerHTML == "") {
        messagesEl.innerHTML += `<p id="first-message"> ${query} </p>`
    } else {
        messagesEl.innerHTML += `<p class="user-message"> ${query} </p>`
    }
    messagesEl.innerHTML += `<div class="loading"><span class="spinner"></span>Thinking ... </div>`
    localStorage.setItem("currentChat", messagesEl.innerHTML)
    messagesWrapperEl.style.display = "block"
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
    setFetching(false)

    if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
    }

    const data = await response.json()
    console.log("data:", data)

    messagesEl.innerHTML += `<div class="assistant-message"> ${renderData(data)} </div>`
    localStorage.setItem("currentChat", messagesEl.innerHTML)
}

// formEl.addEventListener("submit", async (event) => {
//     event.preventDefault()
//     submitMessage()
// })


formInputEl.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return

    if (event.shiftKey) return

    // plain Enter NEVER gets default behavior
    event.preventDefault()

    // if fetching, do nothing
    if (localStorage.getItem("isFetching") === "true") {
        return
    }

    submitMessage()
    
})