(function () {
  "use strict";

  var renderCount = 0;

  function getMermaidTheme() {
    var scheme = document.body ? document.body.getAttribute("data-md-color-scheme") : null;
    if (!scheme && typeof __md_get === "function") {
      try {
        var palette = __md_get("__palette");
        if (palette && palette.color && palette.color.scheme) {
          scheme = palette.color.scheme;
        }
      } catch (e) {
        scheme = null;
      }
    }
    return scheme === "slate" ? "dark" : "default";
  }

  async function renderMermaid(container) {
    if (typeof mermaid === "undefined") {
      return;
    }

    var root = container || document;
    var elements = root.querySelectorAll(".mermaid, pre.mermaid");
    if (!elements || elements.length === 0) {
      return;
    }

    var theme = getMermaidTheme();
    try {
      mermaid.initialize({
        startOnLoad: false,
        theme: theme,
        securityLevel: "loose",
        fontFamily: "Roboto, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
      });
    } catch (err) {
      console.warn("Mermaid initialize warning:", err);
    }

    for (var i = 0; i < elements.length; i++) {
      var el = elements[i];
      var raw = el.getAttribute("data-mermaid-src");
      if (!raw) {
        raw = el.textContent.trim();
        el.setAttribute("data-mermaid-src", raw);
      }

      if (!raw) continue;

      var diagramId = "mermaid-diagram-" + (++renderCount) + "-" + Math.floor(Math.random() * 10000);
      try {
        var renderResult = await mermaid.render(diagramId, raw);
        el.innerHTML = renderResult.svg;
        el.setAttribute("data-processed", "true");
      } catch (err) {
        console.error("Mermaid render error for diagram:", raw, err);
      }
    }
  }

  // Material for MkDocs instant navigation observable
  if (typeof document$ !== "undefined" && typeof document$.subscribe === "function") {
    document$.subscribe(function () {
      renderMermaid();
    });
  }

  // DOM ready handlers
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      renderMermaid();
    });
  } else {
    renderMermaid();
  }

  // Theme switcher observer
  function setupThemeObserver() {
    if (!document.body) return;
    var observer = new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i++) {
        var mutation = mutations[i];
        if (mutation.type === "attributes" && mutation.attributeName === "data-md-color-scheme") {
          renderMermaid();
          break;
        }
      }
    });
    observer.observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });
  }

  if (document.body) {
    setupThemeObserver();
  } else {
    document.addEventListener("DOMContentLoaded", setupThemeObserver);
  }

  window.__renderMermaid = renderMermaid;
})();
