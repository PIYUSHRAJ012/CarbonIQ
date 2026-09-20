(() => {
    const root = document.documentElement;
    const toggle = document.getElementById("theme-toggle");

    if (!toggle) {
        return;
    }

    const getCurrentTheme = () => {
        return root.getAttribute("data-bs-theme") === "dark"
            ? "dark"
            : "light";
    };

    const updateToggle = (theme) => {
        const icon = toggle.querySelector("i");

        if (!icon) {
            return;
        }

        if (theme === "dark") {
            icon.className = "bi bi-sun-fill";
            toggle.setAttribute("aria-label", "Switch to light mode");
            toggle.setAttribute("title", "Switch to light mode");
        } else {
            icon.className = "bi bi-moon-stars-fill";
            toggle.setAttribute("aria-label", "Switch to dark mode");
            toggle.setAttribute("title", "Switch to dark mode");
        }
    };

    const currentTheme = getCurrentTheme();
    updateToggle(currentTheme);

    toggle.addEventListener("click", () => {
        const nextTheme =
            getCurrentTheme() === "dark"
                ? "light"
                : "dark";

        root.setAttribute("data-bs-theme", nextTheme);
        localStorage.setItem("carboniq-theme", nextTheme);

        updateToggle(nextTheme);
    });
})();