const filters = Array.from(document.querySelectorAll(".filter"));
const cards = Array.from(document.querySelectorAll(".phone-card"));

function applyFilter(value) {
  cards.forEach((card) => {
    const group = card.dataset.group;
    card.hidden = value !== "all" && group !== value;
  });

  filters.forEach((filter) => {
    filter.classList.toggle("active", filter.dataset.filter === value);
  });
}

filters.forEach((filter) => {
  filter.addEventListener("click", () => applyFilter(filter.dataset.filter));
});

applyFilter("all");
