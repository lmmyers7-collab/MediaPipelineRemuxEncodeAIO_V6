// dom/query.js
// Split child of domHelpers.js. Owns shared DOM lookup helpers.

(function () {
  "use strict";

  function createDomQueryModule() {
    function byId(id) {
      return document.getElementById(id);
    }

    return { byId };
  }

  window.__domQueryModule = {
    createDomQueryModule,
  };
})();
