# Interactive lessons in T3 Code

Use this route when T3 HTML tools are available and interaction helps the learner reason: a slider for a parameter, a step button for an execution trace, a diagram with selectable states, or a quiz with feedback. Keep ordinary explanations in prose. Ground the model and page references in the actual lecture or code before building an interaction.

Build a self-contained HTML page with inline CSS and JavaScript. Discover `html_preview` and `html_render`; preview first, inspect errors and layout, then render the finished page inline. Use the host's theme variables, fluid layouts, labelled controls, touch-friendly buttons, and readable math. Keep html/body and the outer wrapper transparent, with no fixed viewport heights. Do not start a server or open a browser tab merely to display it. Follow tool errors if preview needs setup; never claim an unrendered page was shown.

Use a small example with explicit assumptions, initial state, units, and boundary cases. A quiz should explain why an answer is correct and offer reset; a simulation should expose its state and update consistently. Verify representative inputs, reset, and boundary cases before showing it. Keep answer reveals optional when the student wants to attempt a problem first.

Rendered HTML is sandboxed. Do not promise it can read local files, invoke agent tools, send answers back to the conversation, or retain progress across reloads. Ask the learner to report their result when agent feedback is needed. MCP Apps can support richer tool and message interaction when a suitable connected app exists; do not assume one is installed. Save a separate standalone artifact when requested for export. Keep portable Markdown notes as the source for Obsidian exports.

Outside T3, use the environment's available artifact/visual tools or a worked text example. Do not require T3 for the lesson.
