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
    scrollToBottomUser()
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

function scrollToBottomUser() {
    const messages = document.querySelectorAll(".msg")
    const lastMessage = messages[messages.length-1]
    console.log("lastMessage:", lastMessage?.innerText)
    console.dir(lastMessage)
    if (lastMessage) {
        lastMessage.scrollIntoView({ behavior: 'smooth' })

    }
}

function scrollToBottomAssistant() {
    const messages = document.querySelectorAll(".assistant-message")
    const lastMessage = messages[messages.length-1]
    console.log("lastMessage:", lastMessage?.innerText)
    console.dir(lastMessage)
    if (lastMessage) {
        lastMessage.scrollIntoView({
            behavior: "smooth",
            block: "end"
        })
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
        scrollToBottomUser()
    }, 10);


    let response

    // ----- ‼️ Handling Fetch Error and Server Error -----
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
            console.log("BAD API RESPONSE")
            handleBadAPIResponse(response)
            return
        }

    } catch(err) {
        let message = `A fetch/network error occurred. Please check your network and try again. 
        If this issue persists, please contact the dev team.`
        finishLoading("error-message", message)
        return 

    }
    // -----

    let finalData
    // Handling SSE stream
    let reader

    // ----- ‼️If reader failed, handle error -----
    try {
        reader = response.body.getReader()
    } catch (error) {
        let message = `An error occured while initializing reader. Please check your 
        network and try again. If this issue persists, please contact the dev team.`
        finishLoading("error-message", message)
        return
    }


    const decoder = new TextDecoder()
    let buffer = ""
    const responseId = `response-${crypto.randomUUID()}`
    messagesEl.innerHTML += `<div id="${responseId}" class="assistant-message"></div>`
    const responseEl = document.getElementById(responseId)
    let streamedHtml = ""
    let chunkCounter = 0

    /* ------------------------------------
     * Stream processing
    --------------------------------------- */
    while (true) {
        let value
        let done
        let readResult

        // ----- ‼️If the stream died due to network, reader would throw error -----
        try {
        readResult = await reader.read()
        } catch (error) {
            let message = `An error occured with Reader while reading response stream. Please check your 
            network and try again. If this issue persists, please contact the dev team.`
            finishLoading("error-message", message)
            return
        }

        value = readResult.value
        done = readResult.done

        // ----- ‼️If the stream shuts down but the response is incomplete, report it here-----
        if (done && !finalData) {
            let message = `Something went wrong while generating response. Please try again. 
            If this issue persists, please contact the dev team.`
            finishLoading("error-message", message)
            return
        }

        if (done) {
            break
        }
        
        buffer += decoder.decode(value, { stream: true }) //grabbing each SSE data event
        const events = buffer.split("\n\n") //each complete package would be delimited by \n\n, so this grabs each event
        buffer = events.pop()  // keep incomplete event (split will produce "" as the last element if all events are complete)

        if (events.length === 0) continue

        for (const event of events) {
            if (!event.startsWith("data: ")) continue
            const jsonString = event.slice(6)
            const data = JSON.parse(jsonString)

            if (data.type === "final") {
                finalData = data.output
                break
            }

            // ----- ‼️If an error occurred in events from the api, handle it here-----
            if (data.type === "error") {
                console.log("GOT ERROR EVENT")
                
                let message = `Something went wrong while processing your request. Please try again. 
                If this issue persists, please contact the dev team.`
                finishLoading("error-message", message)
                return
            }

            const loadingEl = document.querySelector(".loading")
            if (loadingEl && data.type === "progress") {
                loadingEl.innerHTML = `<span class="spinner"></span>${data.output.html}`
            }
            if (data.type == "summarizing") {
                chunkCounter += 1
                streamedHtml += data.output.html
                responseEl.innerHTML = streamedHtml.replaceAll("\\n", "")
                if (chunkCounter % 50 === 0) {
                setTimeout(() => {
                    scrollToBottomAssistant()
                }, 10);
            }
            }
        }
    }

    if (streamedHtml) {
        finishLoadingStream()
    } else {
        responseEl.remove()
        finishLoading("assistant-message", finalData.html)
    }
    console.log("FULL HTML:", responseEl.innerHTML)
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


// ----- ERROR HANDLERS -----

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
    } else {
        userMessage = `The request failed (${response.status}). Please try again.`
    }
    finishLoading("error-message", userMessage)
}

// ----- CLEANUP FUNCTIONS -----

function finishLoading(divClass, message) {
    document.querySelector(".loading")?.remove()
    setFetching(false)
    messagesEl.innerHTML += `<div class="${divClass}"> ${message} </div>`
    localStorage.setItem("currentChat", messagesEl.innerHTML)
}

function finishLoadingStream() {
    document.querySelector(".loading")?.remove()
    setFetching(false)
    localStorage.setItem("currentChat", messagesEl.innerHTML)
}