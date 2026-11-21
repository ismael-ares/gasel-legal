(() => {
  const root = document.documentElement;
  const button = document.getElementById("theme-btn");
  const prefersReduced = matchMedia("(prefers-reduced-motion: reduce)");

  const savedTheme = () => {
    try {
      return localStorage.getItem("gasel-legal-theme");
    } catch (_) {
      return null;
    }
  };
  function setTheme(theme, animate = false) {
    const change = () => {
      if (theme) root.dataset.theme = theme;
      else delete root.dataset.theme;
      if (button) {
        const dark =
          theme === "dark" ||
          (!theme && matchMedia("(prefers-color-scheme: dark)").matches);
        button.classList.toggle("is-dark", dark);
        button.setAttribute("aria-pressed", String(dark));
        button.setAttribute(
          "aria-label",
          dark ? button.dataset.lightLabel : button.dataset.darkLabel,
        );
      }
    };
    if (animate && !prefersReduced.matches && document.startViewTransition) {
      const rect = button.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;
      const radius = Math.hypot(
        Math.max(x, innerWidth - x),
        Math.max(y, innerHeight - y),
      );
      const direction = theme === "dark" ? "vt-to-dark" : "vt-to-light";
      root.classList.add(direction);
      const transition = document.startViewTransition(change);
      transition.ready
        .then(() => {
          root.animate(
            {
              clipPath: [
                `circle(0px at ${x}px ${y}px)`,
                `circle(${radius}px at ${x}px ${y}px)`,
              ],
            },
            {
              duration: 680,
              easing: "cubic-bezier(.2, 0, 0, 1)",
              pseudoElement: "::view-transition-new(root)",
            },
          );
          root.animate(
            {
              transform: ["scale(1)", "scale(.97)"],
              filter: ["brightness(1)", "brightness(.8)"],
            },
            {
              duration: 680,
              easing: "cubic-bezier(.3, 0, .8, .15)",
              pseudoElement: "::view-transition-old(root)",
            },
          );
        })
        .catch(() => {});
      const clearDirection = () =>
        root.classList.remove("vt-to-dark", "vt-to-light");
      transition.finished.then(clearDirection, clearDirection);
    } else if (animate && !prefersReduced.matches) {
      root.classList.add("theme-fade");
      change();
      setTimeout(() => root.classList.remove("theme-fade"), 450);
    } else change();
  }
  const initial = savedTheme();
  setTheme(initial === "light" || initial === "dark" ? initial : null);
  button?.addEventListener("click", () => {
    const active =
      root.dataset.theme ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = active === "dark" ? "light" : "dark";
    try {
      localStorage.setItem("gasel-legal-theme", next);
    } catch (_) {
      /* Selection still applies to this page. */
    }
    setTheme(next, true);
  });

  const search = document.getElementById("language-search");
  const list = document.querySelector(".lang-list");
  const empty = document.querySelector(".lang-empty");
  search?.addEventListener("input", () => {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    list?.querySelectorAll("li").forEach((item) => {
      const match = item.textContent.toLocaleLowerCase().includes(query);
      item.hidden = !match;
      if (match) visible += 1;
    });
    if (empty) empty.hidden = visible > 0;
  });
  document.querySelector(".lang")?.addEventListener("toggle", (event) => {
    if (event.target.open) search?.focus();
  });
  document.querySelector(".lang-list")?.addEventListener("click", (event) => {
    const link = event.target.closest("a.lang-item");
    if (link && location.hash) {
      const destination = new URL(link.href);
      destination.hash = location.hash;
      link.href = destination.href;
    }
  });

  const nav = document.querySelector(".document-nav");
  const targets = [...document.querySelectorAll("[data-sec]")];
  if (nav && targets.length && "IntersectionObserver" in window) {
    const links = [...nav.querySelectorAll("a[data-nav-target]")];
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        links.forEach((link) => {
          if (link.dataset.navTarget === visible.target.id)
            link.setAttribute("aria-current", "true");
          else link.removeAttribute("aria-current");
        });
      },
      { rootMargin: "-70px 0px -68% 0px", threshold: [0, 0.25, 0.5] },
    );
    targets.forEach((target) => observer.observe(target));
  }
})();
