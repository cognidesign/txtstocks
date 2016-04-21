(function () {

  'use strict';

  angular.module('TxtStocks', [])

  .controller('TxtStocksController', ['$scope', '$log', '$http', '$timeout',
    function($scope, $log, $http, $timeout) {
        $scope.submitButtonText = 'Submit';
        $scope.loading = false;
        $scope.tickererror = false;

        $scope.Results = function() {
            $log.log("test");
            var Input = $scope.ticker;
            $http.post('/txt', {"Body": Input}).
            success(function(results) {
                $log.log(results);
                getStockData(results);
                $scope.stockdata = null;
                $scope.loading = true;
                $scope.tickererror = false;

                $scope.submitButtonText = 'Loading...';
            }).
            error(function(error) {
                $log.log(error);
            });
        };
        function getStockData(jobID) {
            var timeout = "";
            var poller = function() {
                $http.get('/results/'+jobID).
                success(function(data, status, headers, config) {
                    if(status === 202) {
                        $log.log(data, status);
                    } else if (status === 200){
                        $log.log(data);
                        $scope.loading = false;
                        $scope.submitButtonText = "Submit";
                        $scope.stockdata = data;
                        $timeout.cancel(timeout);
                        return false;
                    }
                    timeout = $timeout(poller, 2000);
                }).
                error(function(error) {
                    $log.log(error);
                    $scope.loading = false;
                    $scope.submitButtonText = "Submit";
                    $scope.tickererror = true;
                });
            };
            poller();
        }
    }

  ]);

}());