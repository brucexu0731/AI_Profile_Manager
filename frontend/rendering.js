const renderingFunctions = {
    SUMMARIZE(data) {
        // return /*html*/`
        //     <p>${data.output.overall_summary}</p>
        //     <ul>
        //         ${data.output.results.map(result => /*html*/`
        //             <li>${result.summary}</li>    
        //         `).join('')}
        //     </ul>
        // `
        return data.html
    },
    // "COMPARE": (data) => {
    //     return /*html*/`
            
    //     `
    // }
}

export const renderData = (data) => {
    
    if (data.html) return data.html

    // if there is no html field

    const renderFn = renderingFunctions[data.action]

    if (!renderFn) {
        return `[RENDER FUNCTION "${data.action||'UNKNOWN ACTION'}" NOT YET IMPLEMENTED]`
    }

    return renderFn(data)
}