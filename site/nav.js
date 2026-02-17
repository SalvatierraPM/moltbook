(() => {
  const menus = Array.from(document.querySelectorAll(".nav-menu"));
  if (!menus.length) return;

  const closeAll = (except = null) => {
    for (const menu of menus) {
      if (menu !== except) {
        menu.removeAttribute("open");
      }
    }
  };

  for (const menu of menus) {
    menu.addEventListener("toggle", () => {
      if (menu.open) {
        closeAll(menu);
      }
    });

    const links = menu.querySelectorAll(".nav-menu-panel a");
    for (const link of links) {
      link.addEventListener("click", () => {
        menu.removeAttribute("open");
      });
    }
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (menus.some((menu) => menu.contains(target))) return;
    closeAll();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAll();
    }
  });
})();
