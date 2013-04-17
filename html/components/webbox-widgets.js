
/* base file to include for all webbox-widgets,
   including :
      modeltable
*/

(function() {
	angular
		.module('webbox-widgets', ['ui'])
		.factory('webbox',function() {
			var exports = {};
			var d = exports.loaded = new $.Deferred();
			exports.safe_apply = function($scope, fn) {
				if ($scope.$$phase !== undefined) {
					return fn();
				}
				$scope.$apply(fn);
			};			
			WebBox.load().then(function() {
				exports.u = window.u = WebBox.utils;
				exports.store = window.store = new WebBox.Store();
				window.store.fetch().then(function() {
					d.resolve(exports);
				}).fail(function() {
					// TODO
					u.error('Error fetching boxes');
				});
			});
			return exports;
		});	
}());