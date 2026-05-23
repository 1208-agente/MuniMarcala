const navToggle = document.querySelector("[data-nav-toggle]");
const navToggleBottom = document.querySelector("[data-nav-toggle-bottom]");
const navClose = document.querySelector("[data-nav-close]");
const navScrim = document.querySelector("[data-nav-scrim]");
const nav = document.querySelector("[data-nav]");

if (navToggle && nav) {
  const closeNav = () => {
    nav.classList.remove("open");
    document.body.classList.remove("nav-open");
    navToggle.setAttribute("aria-expanded", "false");
    document.querySelectorAll(".nav-dropdown[open]").forEach((dropdown) => {
      dropdown.removeAttribute("open");
    });
  };

  const openNav = () => {
    nav.classList.add("open");
    document.body.classList.add("nav-open");
    navToggle.setAttribute("aria-expanded", "true");
    if (navClose) {
      navClose.focus({ preventScroll: true });
    }
  };

  const toggleNav = (event) => {
    event.stopPropagation();
    event.preventDefault();
    if (nav.classList.contains("open")) {
      closeNav();
    } else {
      openNav();
    }
  };

  navToggle.addEventListener("click", toggleNav);
  if (navToggleBottom) {
    navToggleBottom.addEventListener("click", toggleNav);
  }
  if (navClose) {
    navClose.addEventListener("click", closeNav);
  }
  if (navScrim) {
    navScrim.addEventListener("click", closeNav);
  }

  document.addEventListener("click", (event) => {
    if (
      !nav.contains(event.target) &&
      !navToggle.contains(event.target) &&
      (!navToggleBottom || !navToggleBottom.contains(event.target))
    ) {
      closeNav();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeNav();
    }
  });

  nav.addEventListener("click", (event) => {
    event.stopPropagation();
    if (event.target.closest("a")) {
      closeNav();
    }
  });

  document.querySelectorAll(".nav-dropdown > summary").forEach((summary) => {
    summary.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const dropdown = summary.parentElement;
      const shouldOpen = !dropdown.open;
      document.querySelectorAll(".nav-dropdown[open]").forEach((other) => {
        if (other !== dropdown) {
          other.removeAttribute("open");
        }
      });
      if (shouldOpen) {
        dropdown.setAttribute("open", "");
      } else {
        dropdown.removeAttribute("open");
      }
    });
  });
}

const heroRotator = document.querySelector("[data-hero-rotator]");
const heroSlides = heroRotator ? Array.from(heroRotator.querySelectorAll(".hero-slide")) : [];
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

if (heroSlides.length > 1 && !prefersReducedMotion) {
  let currentHeroSlide = 0;
  window.setInterval(() => {
    heroSlides[currentHeroSlide].classList.remove("active");
    currentHeroSlide = (currentHeroSlide + 1) % heroSlides.length;
    heroSlides[currentHeroSlide].classList.add("active");
  }, 6500);
}
