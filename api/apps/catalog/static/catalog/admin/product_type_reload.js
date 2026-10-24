// On the add page, choosing a product type reloads the form with ?product_type=<id>, so the
// attribute fields of that type appear (T3.4). The name is kept; nothing else is typed yet.
document.addEventListener("DOMContentLoaded", function () {
  var select = document.getElementById("id_product_type");
  if (!select || !/\/add\/$/.test(window.location.pathname)) return;
  select.addEventListener("change", function () {
    var params = new URLSearchParams();
    if (select.value) params.set("product_type", select.value);
    var name = document.getElementById("id_name");
    if (name && name.value) params.set("name", name.value);
    window.location.search = params.toString();
  });
});
