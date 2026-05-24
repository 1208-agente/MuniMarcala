var navToggle = document.querySelector("[data-nav-toggle]");
var navToggleBottom = document.querySelector("[data-nav-toggle-bottom]");
var navClose = document.querySelector("[data-nav-close]");
var nav = document.querySelector("[data-nav]");

if (navToggle && nav) {
  function closeNav() {
    nav.classList.remove("open");
    document.body.classList.remove("nav-open");
    navToggle.setAttribute("aria-expanded", "false");
    var openDropdowns = document.querySelectorAll(".nav-dropdown[open]");
    for (var i = 0; i < openDropdowns.length; i += 1) {
      openDropdowns[i].removeAttribute("open");
    }
  }

  function openNav() {
    nav.classList.add("open");
    document.body.classList.add("nav-open");
    navToggle.setAttribute("aria-expanded", "true");
  }

  function toggleNav(event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    if (document.body.classList.contains("nav-open")) {
      closeNav();
    } else {
      openNav();
    }
  }

  navToggle.addEventListener("click", toggleNav);

  if (navToggleBottom) {
    navToggleBottom.addEventListener("click", toggleNav);
  }

  if (navClose) {
    navClose.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      closeNav();
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" || event.keyCode === 27) {
      closeNav();
    }
  });

  document.addEventListener("click", function (event) {
    if (!document.body.classList.contains("nav-open")) return;
    if (nav.contains(event.target)) return;
    if (navToggle.contains(event.target)) return;
    if (navToggleBottom && navToggleBottom.contains(event.target)) return;
    closeNav();
  });

  nav.addEventListener("click", function (event) {
    event.stopPropagation();
    if (event.target.closest && event.target.closest("a")) {
      closeNav();
    }
  });

  window.addEventListener("scroll", function () {
    if (document.body.classList.contains("nav-open")) return;
    var openDropdowns = document.querySelectorAll(".nav-dropdown[open]");
    for (var i = 0; i < openDropdowns.length; i += 1) {
      openDropdowns[i].removeAttribute("open");
    }
  });

  var summaries = document.querySelectorAll(".nav-dropdown > summary");
  for (var i = 0; i < summaries.length; i += 1) {
    summaries[i].addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      var dropdown = this.parentElement;
      var shouldOpen = !dropdown.open;
      var openDropdowns = document.querySelectorAll(".nav-dropdown[open]");
      for (var j = 0; j < openDropdowns.length; j += 1) {
        if (openDropdowns[j] !== dropdown) {
          openDropdowns[j].removeAttribute("open");
        }
      }
      if (shouldOpen) {
        dropdown.setAttribute("open", "");
      } else {
        dropdown.removeAttribute("open");
      }
    });
  }
}

var heroRotator = document.querySelector("[data-hero-rotator]");
var heroSlides = heroRotator ? Array.prototype.slice.call(heroRotator.querySelectorAll(".hero-slide")) : [];
var prefersReducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

if (heroSlides.length > 1 && !prefersReducedMotion) {
  var currentHeroSlide = 0;
  window.setInterval(function () {
    heroSlides[currentHeroSlide].classList.remove("active");
    currentHeroSlide = (currentHeroSlide + 1) % heroSlides.length;
    heroSlides[currentHeroSlide].classList.add("active");
  }, 6500);
}
