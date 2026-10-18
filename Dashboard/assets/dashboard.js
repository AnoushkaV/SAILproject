// Functions used by Dash components (slider tooltip): slot number -> clock time.
window.dccFunctions = window.dccFunctions || {};
window.dccFunctions.slotToTime = function (slot) {
  var minutes = Math.round(slot) * 3;
  var h = Math.floor(minutes / 60), m = minutes % 60;
  return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m;
};
window.dccFunctions.hourLabel = function (h) {
  return (h < 10 ? "0" : "") + Math.round(h) + ":00";
};
