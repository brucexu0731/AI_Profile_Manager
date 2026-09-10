import { renderData } from "./rendering.js"

const messagesEl = document.getElementById("messages")
const messagesWrapperEl = document.getElementById("messages-wrapper")
const formEl = document.getElementById("chat-form")
const formInputEl = document.getElementById("query")
const sessionIdEl = document.getElementById("session-id")
const sessionEl = document.getElementById("session")
const headerEl = document.getElementById("header")
const titleEl = document.querySelector("#header > h2")

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

function toggleChat(){
    messagesWrapperEl.style.display = "block"
    sessionEl.style.display = "block"
    headerEl.style.display = "none"
}

function toggleHome(){
    messagesWrapperEl.style.display = "none"
    sessionEl.style.display = "none"
    headerEl.style.display = "block"
}



//initialize sessionId
let sessionId = getSessionId() || newSessionId()
sessionIdEl.textContent = sessionId

//Reload chat history
let chatHistory = getChat()
messagesEl.innerHTML = chatHistory
if (messagesEl.innerHTML == ""){
    toggleHome()
} else {
    toggleChat()
    scrollToBottom()
}

//Check if any llm is still processing
const isFetching = localStorage.getItem("isFetching") === "true"
clearHistoryBtn.disabled = isFetching

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

    toggleHome()
    restartAnimations()
}

function restartAnimations() {
    titleEl.style.animation = "none"
    formEl.style.animation = "none"

    void headerEl.offsetWidth

    titleEl.style.animation = ""
    formEl.style.animation = ""
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

function scrollToBottom() {
    const messages = document.querySelectorAll(".msg")
    const lastMessage = messages[messages.length-1]
    console.log("lastMessage:", lastMessage?.innerText)
    console.dir(lastMessage)
    if (lastMessage) {
        lastMessage.scrollIntoView({ behavior: 'smooth' })

    }
}

async function submitMessage() {
    const query = formInputEl.value
    formInputEl.value = ""

    //disallow clear history while fetching data
    setFetching(true)

    if (messagesEl.innerHTML == "") {
        messagesEl.innerHTML += `<p class="msg" id="first-message"> ${query} </p>`
    } else {
        messagesEl.innerHTML += `<p class="msg user-message"> ${query} </p>`
    }
    messagesEl.innerHTML += `<div class="loading"><span class="spinner"></span>Thinking ... </div>`
    localStorage.setItem("currentChat", messagesEl.innerHTML)
    toggleChat()

    // find the new message element and scroll to it
    setTimeout(() => {
        scrollToBottom()
    }, 10);


    let response
    try {
        response = await fetch(`/agent/${sessionId}/ask-stream`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                query: query
            })
        })

        if (!response.ok) {
            // ❗❗❗
            console.log("BAD API RESPONSE")
            handleBadAPIResponse(response)
            return
        }

    } catch(err) {
        //need to make sure this works 

        let message = `A fetch/network error occurred. Please check your network and try again. 
        If this issue persists, please contact the dev team.`
        finishLoading("error-message", message)
        return 

    }

    let finalData
    // Handling SSE stream
    let reader
    try {
        reader = response.body.getReader()
    } catch (error) {
        // ❗❗❗
        handleMissingReader(response, error)
        return
    }
    const decoder = new TextDecoder()
    let buffer = ""

    while (true) {
        let value
        let done
        try {
            const readResult = await reader.read()
            value = readResult.value
            done = readResult.done
        } catch (error) {
            // ❗❗❗
            handleReadError(error)
            break
        }

        if (done && !finalData) {
            // ❗❗❗
            handleNoFinalData()
            break
        }

        if (done && finalData.type === 'error') {
            // ❗❗❗
            handleSseError(finalData)
            break
        }

        if (done) {
            break
        }

        buffer += decoder.decode(value, { stream: true })

        const events = buffer.split("\n\n")
        buffer = events.pop()  // keep incomplete event
        if (events.length === 0) continue

        const event = events[events.length - 1]
        if (!event.startsWith("data: ")) continue
        const jsonString = event.slice(6)
        const data = JSON.parse(jsonString)

        if (data.type === "final") {
            finalData = data.output
            break
        }

        const loadingEl = document.querySelector(".loading")
        if (loadingEl) {
            loadingEl.innerHTML = `<span class="spinner"></span>${data.output.html}`
        }
    }

    finishLoading("assistant-message", renderData(finalData))
    console.log("data:", finalData)
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


// ----- ERROR HANDLING -----

function handleBadAPIResponse(response){
    let userMessage = ""
    if (response.status === 400) {
        userMessage = `Our system detected an invalid HTTP request, please try again. 
        If this issue persists, please contact the dev team.`
    } else if (response.status === 404) {
        userMessage = `LLM server was not found / cannot be reached, please try again. 
        If this issue persists, please contact the dev team.`
    } else if (response.status >= 500) {
        userMessage = `An internal server error occurred, please try again. If this issue 
        persists, please contact the dev team.`
    }
    finishLoading("error-message", userMessage)
}

function finishLoading(divClass, message) {
    document.querySelector(".loading")?.remove()
    setFetching(false)
    messagesEl.innerHTML += `<div class="${divClass}"> ${message} </div>`
    localStorage.setItem("currentChat", messagesEl.innerHTML)
}