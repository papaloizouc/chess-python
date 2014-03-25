var chess = angular.module('chess');
chess.controller('NavBarCtrl',
    function ($scope, $cookies, $rootScope, $modal, UserService) {


        $scope.login = function (_username) {
            UserService.login(_username);
        };

        $scope.logout = function () {
            UserService.logout();
        };


        $scope.init = function () {
            if ($cookies.username) {
                $rootScope.logged_in = $cookies.username;
            }
        };
        $scope.dropdown_clicked = function (e) {
            e.preventDefault();
            e.stopPropagation();
        };

        $scope.sign_in_clicked = function () {
            var modalInstance = $modal.open({
                templateUrl: 'templates/modal.html',
                //controller: ModalInstanceCtrl,
                resolve: {
                    items: function () {
                        return $scope.items;
                    }
                }
            });
        };

    });


//myApp.controller('TestCtrl', ['$scope', '$log', '$http',
//    function ($scope, $log, $http) {
//        //use only for testing
//    }]);
