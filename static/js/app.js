const navToggle = document.querySelector("[data-nav-toggle]");
const nav = document.querySelector("[data-nav]");

if (navToggle && nav) {
  navToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    const isOpen = nav.classList.toggle("open");
    navToggle.setAttribute("aria-expanded", String(isOpen));
  });

  document.addEventListener("click", (event) => {
    if (!nav.contains(event.target) && !navToggle.contains(event.target)) {
      nav.classList.remove("open");
      navToggle.setAttribute("aria-expanded", "false");
      document.querySelectorAll(".nav-dropdown[open]").forEach((dropdown) => {
        dropdown.removeAttribute("open");
      });
    }
  });

  nav.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      nav.classList.remove("open");
      navToggle.setAttribute("aria-expanded", "false");
      document.querySelectorAll(".nav-dropdown[open]").forEach((dropdown) => {
        dropdown.removeAttribute("open");
      });
    }
  });

  document.querySelectorAll(".nav-dropdown").forEach((dropdown) => {
    dropdown.addEventListener("toggle", () => {
      if (dropdown.open) {
        document.querySelectorAll(".nav-dropdown[open]").forEach((other) => {
          if (other !== dropdown) {
            other.removeAttribute("open");
          }
        });
      }
    });
  });
}
