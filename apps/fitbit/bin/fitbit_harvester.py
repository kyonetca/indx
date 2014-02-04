import logging, json, argparse, sys, os, uuid, urllib2
# import logging.config
import keyring, keyring.util.platform_
from keyring.backends.pyfs import PlaintextKeyring
from fitbit import Fitbit, FitbitResources, FitbitIntraDay
from indxclient import IndxClient, IndxClientAuth
import oauth2 as oauth
from time import sleep
from datetime import date, datetime, timedelta, time
from twisted.internet.defer import Deferred, DeferredList
from twisted.internet import reactor, threads

class FitbitHarvester:

    def __init__(self):
        log_handler = logging.FileHandler("fitbit_harvester.log", "a")
        log_handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter('%(name)s\t%(levelname)s\t%(asctime)s\t%(message)s')
        log_handler.setFormatter(formatter)
    
        self.logger = logging.getLogger() 
        self.logger.setLevel(logging.DEBUG)
        for handler in self.logger.handlers: # remove default handler
            self.logger.removeHandler(handler)
        self.logger.addHandler(log_handler)
    
        data_root = keyring.util.platform_.data_root()
        if not os.path.exists(data_root):
            os.mkdir(data_root)
        keyring.set_keyring(PlaintextKeyring())

        self.parser = argparse.ArgumentParser(prog="run")
        self.parser.add_argument('--config', help="Set config (input requires JSON) and exit.")
        self.parser.add_argument('--get-config', action="store_true", help="Output current config as JSON and exit.")
        self.parser.add_argument('--server', help="The server URL to connect to.")

        # init fitbit
        consumer_key = "9cc7928d03fa4e1a92eda0d01ede2297"
        consumer_secret = "340ea36a974e47738a335c0cccfe1fcf"
        self.fitbit = Fitbit(consumer_key, consumer_secret)
        self.fitbit_resources = None
        self.fitbit_intraday = None

        self.api_calls_left = 150 # limited to 150 per hour per user per app 
        self.version = 0

        self.user = None
        self.devices = []
        self.harvester = None

        self.user_id = ""
        self.harvester_id = ""
        self.steps_ts_id = ""
        self.calories_ts_id = ""
        self.distance_ts_id = ""
        self.floors_ts_id = ""
        self.elevation_ts_id = ""

    def set_config(self, args):
        stored_config_harvester = keyring.get_password("INDX", "INDX_Fitbit_Harvester")
        if stored_config_harvester is not None:
            stored_config_harvester = json.loads(stored_config_harvester)
        stored_config_fitbit = keyring.get_password("Fitbit.com", "Fitbit")
        if stored_config_fitbit is not None:
            stored_config_fitbit = json.loads(stored_config_fitbit)

        received_config = json.loads(args['config'])
        if (type(received_config) != dict):
            received_config = json.loads(received_config)
        self.logger.debug("Received config: {0}".format(received_config))
        config = {}
        if 'fitbit' in received_config:
            fitbit_config = received_config['fitbit']
            if fitbit_config and ('pin' in fitbit_config) and ('req_token' in fitbit_config): # this should check for the req_token in the stored config!
                self.logger.debug("Received pin: {0}".format(fitbit_config['pin']))
                try:
                    token = self.fitbit.get_token_with_pin(fitbit_config['pin'], fitbit_config['req_token'])
                    self.api_calls_left = self.api_calls_left - 1
                    self.logger.debug("Got auth token {0}".format(token))
                    self.logger.debug("Got auth token of type {0}".format(type(token)))
                    if token:
                        config['token']=token
                        keyring.set_password("Fitbit.com", "Fitbit", json.dumps(config))
                except Exception as exc:
                    self.logger.error("Could not authorise to fitbit, with pin {0}, error: {1}".format(fitbit_config['pin'], exc))
        if 'harvester' in received_config:
            harvester_config = received_config['harvester']
            if harvester_config != stored_config_harvester:
                keyring.set_password("INDX", "INDX_Fitbit_Harvester", json.dumps(harvester_config)) 

    def get_config(self, args):
        stored_config_harvester = keyring.get_password("INDX", "INDX_Fitbit_Harvester")
        stored_config_fitbit = keyring.get_password("Fitbit.com", "Fitbit")

        self.logger.debug("Loaded harvester config from keyring: {0}".format(stored_config_harvester))
        self.logger.debug("Loaded fitbit config from keyring: {0}".format(stored_config_fitbit))

        if stored_config_fitbit is None :
            token_url = self.fitbit.get_token_url()
            self.api_calls_left = self.api_calls_left - 1
            config_fitbit = {}
            config_fitbit["url"] = token_url['url']
            config_fitbit["req_token"] = token_url['req_token']
        else :
            if (type(stored_config_fitbit) != dict):
                config_fitbit = json.loads(stored_config_fitbit)
            if (type(config_fitbit) != dict):
                config_fitbit = json.loads(config_fitbit)
            if 'token' not in config_fitbit :
                token_url = self.fitbit.get_token_url()
                self.api_calls_left = self.api_calls_left - 1
                config_fitbit["url"] = token_url['url']
                config_fitbit["req_token"] = token_url['req_token']
                keyring.set_password("Fitbit.com", "Fitbit", json.dumps(config_fitbit))
        if stored_config_harvester is None:
            return json.dumps({"fitbit":config_fitbit}) # don't send the req_token
        return json.dumps({"fitbit":config_fitbit, "harvester":json.loads(stored_config_harvester)}) # don't send the req_token

    def check_configuration(self):
        stored_config_harvester = keyring.get_password("INDX", "INDX_Fitbit_Harvester")
        self.logger.debug("stored_config_harvester type: {0}".format(type(stored_config_harvester)))
        self.logger.debug("Loaded harvester config from keyring: {0}".format(stored_config_harvester))
        if stored_config_harvester is None :
            self.logger.error("Harvester not configured. Please configure before use.")
            sys.exit(1)
        if (type(stored_config_harvester) != dict):
            stored_config_harvester = json.loads(stored_config_harvester)
            self.logger.debug("stored_config_harvester type (after 1 loads): {0}".format(type(stored_config_harvester)))

        if self.fitbit.get_token() is None:
            stored_config_fitbit = keyring.get_password("Fitbit.com", "Fitbit")
            self.logger.debug("stored_config_fitbit type: {0}".format(type(stored_config_fitbit)))
            self.logger.debug("Loaded fitbit config from keyring: {0}".format(stored_config_fitbit))

            token = None
            if stored_config_fitbit is None :
                self.logger.error("Not authenticated to Fitbit.com. Please configure before use.")
                sys.exit(1)
            else :
                if (type(stored_config_fitbit) != dict):
                    stored_config_fitbit = json.loads(stored_config_fitbit)
                    self.logger.debug("stored_config_fitbit type (after 1 loads): {0}".format(type(stored_config_fitbit)))
                if 'token' not in stored_config_fitbit :
                    self.logger.debug("Could not find Fitbit auth token in keyring");
                    if ('pin' in stored_config_fitbit) and ('req_token' in stored_config_fitbit):
                        self.logger.debug("Found pin {0} and req_token in keyring, attempting authorization to Fitbit.com".format(stored_config_fitbit['pin']))
                        try:
                            fitbit_token_config = {}
                            token = self.fitbit.get_token_with_pin(stored_fitbit_config['pin'], stored_fitbit_config['req_token'])
                            self.api_calls_left = self.api_calls_left - 1
                            if token:
                                self.logger.debug("Got auth token {0}".format(token))
                                # self.logger.debug("Got auth token of type {0}".format(type(token)))
                                fitbit_token_config['token']=token
                            keyring.set_password("Fitbit.com", "Fitbit", json.dumps(fitbit_token_config))
                        except Exception as exc:
                            self.logger.error("Could not authorise to fitbit, error: {1}".format(exc))
                            sys.exit(1)
                    else :
                        self.logger.debug("Could not find pin or req_token in keyring. Cannot attempt authorization to Fitbit.com.")
                        sys.exit(1)
                else: 
                    token = stored_config_fitbit['token']
            if token is not None :
                self.fitbit.set_token(token)
        return stored_config_harvester['start'], stored_config_harvester['box'], stored_config_harvester['user'], stored_config_harvester['password']

    def run(self):
        args = vars(self.parser.parse_args())
        self.logger.debug("Received arguments: {0}".format(args))
        if args['config']:
            self.set_config(args)
        elif args['get_config']:
            print self.get_config(args)
        else:
            self.logger.debug("Starting the harvester. ")
            self.work(args['server'])
            reactor.run()
         
    def work(self, server_url):
        start, box, user, password = self.check_configuration()

        self.fitbit_resources = FitbitResources(self.fitbit)
        self.logger.debug("Created FitbitResources.")

        self.fitbit_intraday = FitbitIntraDay(self.fitbit)
        self.logger.debug("Created FitbitIntraDay.")

        def indx_cb(indx):
            self.logger.debug("Created INDXClient.")
            r_d = Deferred()

            def udev_cb(indx):
                self.logger.debug("Found or created user and devices.")

                def timeseries_cb(indx):
                    self.logger.debug("Found or created all 5 time series.")
                    devs = []
                    for dev in self.devices:
                        devs.append(dev["@id"])
                
                    def harvester_cb(harv, indx=indx, devs=devs):
                        harv_d = Deferred()
                        self.harvester = harv
                        if not self.harvester:
                            self.harvester = {"@id":self.harvester_id,"label":"INDX Fitbit Harvester meta info"}
                        self.harvester.update({"user":self.user_id, "devices":devs})
                        self.safe_update(indx, self.harvester).addCallbacks(harv_d.callback, harv_d.errback)
                        return harv_d

                    def harvest_cb(x, indx=indx):
                        def wait(y):
                            self.logger.debug("Harvested! Suspending execution for 1 hours at {0}.".format(datetime.now().isoformat()))
                            sleep(30)
                            # sleep(3600)
                            r_d.callback(None)

                        self.harvest(indx).addCallbacks(wait, r_d.errback)
                
                    self.harvester_id = "fitbit_harvester_{0}".format(self.user["encodedId"])
                    self.find_create(indx, self.harvester_id, {"label":"INDX Fitbit Harvester meta info", "user":self.user_id, "devices":devs}).addCallbacks(harvester_cb, r_d.errback).addCallbacks(harvest_cb, r_d.errback)

                self.find_create_timeseries(indx).addCallbacks(timeseries_cb, r_d.errback)

            self.user = None
            self.devices = []
            self.user_id = ""
            self.find_create_user_and_devices(indx).addCallbacks(udev_cb, r_d.errback)
            return r_d

        def loop(x=None):
            self.get_indx(server_url, box, user, password).addCallbacks(indx_cb, lambda failure: self.logger.error("Error getting indx: {0}".format(failure))).addCallbacks(loop, lambda f: self.logger.error("Error harvesting: {0}".format(f)))

        threads.deferToThread(loop)

    def get_indx(self, server_url, box, user, password):
        return_d = Deferred()
        def authed_cb(): 
            def token_cb(token):
                indx = IndxClient(server_url, box, "INDX_Fitbit_Harvester", token = token, client = authclient.client)
                return_d.callback(indx)

            authclient.get_token(box).addCallbacks(token_cb, return_d.errback)
            
        authclient = IndxClientAuth(server_url, "INDX_Fitbit_Harvester")
        authclient.auth_plain(user, password).addCallbacks(lambda response: authed_cb(), return_d.errback)
        return return_d

    def find_create_user_and_devices(self, indx):
        return_d = Deferred()
        
        def user_cb(x, indx=indx):

            def dev_cb(results):
                self.logger.debug("defereds results: {0}".format(results))
                for (success, value) in results:
                    if not success:
                        return_d.errback(value)
                return_d.callback(indx)
            
            fitbit_devices = self.fitbit_resources.get_devices()
            # [ { 
            # "battery": "Medium",
            # "deviceVersion": "One",
            # "id": "123456",
            # "lastSyncTime": "2014-02-02T00:09:20.000",
            # "mac": "ASDF1234GHJK5678",
            # "type": "TRACKER"
            # } ]
            self.logger.debug("Got fitbit devices: {0}".format(fitbit_devices))
            deferreds = []
            for fdev in fitbit_devices:
                self.logger.debug("Searching for device {0}".format(fdev))
                deferreds.append(self.find_create_device(indx, fdev))
            DeferredList(deferreds).addCallbacks(dev_cb, return_d.errback)

        fitbit_user = self.fitbit_resources.get_user_info()
        # { "user":  {
        #     "avatar": "https://url",
        #     "avatar150": "https://url",
        #     "city": "London",
        #     "country": "GB",
        #     "dateOfBirth": "1970-01-01",
        #     "displayName": "name",
        #     "distanceUnit": "METRIC",
        #     "encodedId": "123ASD4F",
        #     "foodsLocale": "en_US",
        #     "fullName": "Full Name",
        #     "gender": "FEMALE/MALE",
        #     "glucoseUnit": "METRIC",
        #     "height": x,
        #     "heightUnit": "METRIC",
        #     "locale": "en_GB",
        #     "memberSince": "1970-01-01",
        #     "nickname": "nick",
        #     "offsetFromUTCMillis": 0,
        #     "strideLengthRunning": float,
        #     "strideLengthWalking": float,
        #     "timezone": "Europe/London",
        #     "waterUnit": "METRIC",
        #     "weight": x,
        #     "weightUnit": "METRIC"
        #   } }
        self.find_create_user(indx, fitbit_user).addCallbacks(user_cb, return_d.errback)
        return return_d        

    def find_create_timeseries(self, indx):
        self.steps_ts_id = "fitbit_steps_ts_{0}".format(self.user["encodedId"])
        self.calories_ts_id = "fitbit_calories_ts_{0}".format(self.user["encodedId"])
        self.distance_ts_id = "fitbit_distance_ts_{0}".format(self.user["encodedId"])
        self.floors_ts_id = "fitbit_floors_ts_{0}".format(self.user["encodedId"])
        self.elevation_ts_id = "fitbit_elevation_ts_{0}".format(self.user["encodedId"])
        # should also capture the device as a property
        
        ts_d = Deferred()

        def s_ts_cb(ts, indx=indx):
            self.logger.debug("Found or created steps time series.")

            def c_ts_cb(ts, indx=indx):
                self.logger.debug("Found or created calories time series.")
                
                def d_ts_cb(ts, indx=indx):
                    self.logger.debug("Found or created distance time series.")

                    def e_ts_cb(ts, indx=indx):
                        self.logger.debug("Found or created elevation time series.")
                        
                        def f_ts_cb(ts, indx=indx):
                            self.logger.debug("Found or created floors time series.")
                            ts_d.callback(indx)

                        self.find_create(indx, self.floors_ts_id, {"label":"Fitbit Floors Time Series", "type":"Dataset", "user":self.user_id}).addCallbacks(f_ts_cb, ts_d.errback)
    
                    self.find_create(indx, self.elevation_ts_id, {"label":"Fitbit Elevation Time Series", "type":"Dataset", "user":self.user_id}).addCallbacks(e_ts_cb, ts_d.errback)
                
                self.find_create(indx, self.distance_ts_id, {"label":"Fitbit Distance Time Series", "type":"Dataset", "user":self.user_id}).addCallbacks(d_ts_cb, ts_d.errback)
            
            self.find_create(indx, self.calories_ts_id, {"label":"Fitbit Calories Time Series", "type":"Dataset", "user":self.user_id}).addCallbacks(c_ts_cb, ts_d.errback)

        self.find_create(indx, self.steps_ts_id, {"label":"Fitbit Steps Time Series", "type":"Dataset", "user":self.user_id}).addCallbacks(s_ts_cb, ts_d.errback)
        return ts_d

    def harvest(self, indx):
        harv_d = Deferred()

# memberSince (absolute last day) --- retrieved_from --- retrieved_to --- lastSync (advancing) 
        if "retrieved_to" in self.harverster:
            self.retrieved_to = self.harvester["retrieved_to"]
        elif "memberSince" in self.user:
            self.retrieved_to = self.user["memberSince"]
        else:
            self.retrieved_to = None

        last_sync = self.getLastSyncDayFromDevices() # returns None if not found
        if "retrieved_from" in self.harvester:
            self.retrieved_from = self.harvester["retrieved_from"]
        else 
            self.retrieved_from = last_sync
        
        if "memberSince" in self.user and self.retrieved_from == self.user["memberSince"]:
            # we are done going back in time to retrieve data, we only check for new updates from now on
            pass
        else:
            # we still have to go back in time to retrieve old data, as we have not reached the date when the user became a member
            self.harvest_back(indx).addCallbacks(harv_d.callback, harv_d.errback)

        # once all the old data was retrieved, we can get some of the new remaining data    
        if  (last_sync not None) and self.retrieved_to == last_sync :
            # there was no new sync since the last loop, not having anything new to retrieve
            harv_d.callback(None)
        else:
            # there was a new sync since the last time, there is new data to retrieve
            self.harvest_forward(indx).addCallbacks(harv_d.callback, harv_d.errback)
        
        return harv_d

    def getLastSyncDayFromDevices(self):
        last = None
        for dev in self.devices:
            if "lastSyncTime" in dev:
                last_sync_dev = datetime.strptime(dev["lastSyncTime"], "%Y-%m-%dT%H:%M:%S.000").date()
                if last is None:
                    last = last_sync_dev 
                elif last < last_sync_dev:
                    last = last_sync_dev
        if last is None:
            return None
        return last.strftime("%Y-%m-%d") 

    def harvest_back(self, indx):
        back_d = Deferred()

        def check_cb(x, indx=indx):
            if (self.api_calls_left > 4):
                self.harvest_back(indx).addCallbacks(back_d.callback, back_d.errback)
            else:
                back_d.callback(None)

        prev = datetime.strptime(self.retrieved_from, "%Y-%m-%d").date() + timedelta(days=-1)
        self.retrieved_from = prev.strftime("%Y-%m-%d") 
        # if still after membership day, continue

        points = self.get_day_points(indx, self.retrieved_from) 
        harvester["retrieved_from"] = self.retrieved_from
        self.safe_update(indx, points+[harvester]).addCallbacks(check_cb, back_d.errback)

        return back_d

    def harvest_forward(self, indx):
        fwd_d = Deferred()

        return fwd_d

        # def harvester_cb(harvester, indx=indx):
            
            # def get_day_points(day):
            #     gdp_return_d = Deferred()

            #     def points_cb(pts):
            #         gdp_return_d.callback(pts)

            #     if day.date().isoformat() in self.fetched_days:
            #         self.logger.debug("Data for {0} was already fetched, rechecking!".format(day.date().isoformat()))
            #         self.find_day_points(indx, day).addCallbacks(points_cb, gdp_return_d.errback)
            #     else:
            #         self.logger.debug("Data for {0} was not yet fetched. Getting it now.".format(day.date().isoformat()))
            #         self.fetched_days.append(day.date().isoformat())
            #         gdp_return_d.callback(None)
            #     return gdp_return_d

            # def processing_cb(day_points, day):

            #     # processing steps
            #     steps = self.download_steps(day)

            #     zeros = False
            #     zeros = self.check_all_zero(steps)
            #     if zeros :
            #         self.logger.debug("Step data points are all 0. ")
            #         if self.all_zeros > day:
            #             self.all_zeros = day
            #     else :
            #         self.all_zeros = self.today()

            #     steps_points = []
            #     if day_points and self.steps_ts_id in day_points and day_points[self.steps_ts_id] :
            #         steps_points = self.replace_data_points(day, steps, day_points[self.steps_ts_id], self.steps_ts_id, "http://sociam.org/ontology/health/StepCount")
            #     else:
            #         steps_points = self.create_data_points(day, steps, self.steps_ts_id, "http://sociam.org/ontology/health/StepCount") # a subclass of http://www.qudt.org/qudt/owl/1.0.0/quantity/index.html#Frequency and subclass of http://purl.org/linked-data/cube#Observation
            #     # self.logger.debug("Saving {0} step data points.".format(len(steps_points)))

            #     # processing calories
            #     calories = self.download_calories(day)
            #     calories_points = []
            #     if day_points and self.calories_ts_id in day_points and day_points[self.calories_ts_id] :
            #         calories_points = self.replace_data_points(day, calories, day_points[self.calories_ts_id], self.calories_ts_id, "http://sociam.org/ontology/health/CaloriesBurned")
            #     else:
            #         calories_points = self.create_data_points(day, calories, self.calories_ts_id, "http://sociam.org/ontology/health/CaloriesBurned") # subclass of http://purl.org/linked-data/cube#Observation
            #     # self.logger.debug("Saving {0} calories data points.".format(len(calories_points)))

            #     # processing distance
            #     distance = self.download_distance(day)
            #     distance_points = []
            #     if day_points and self.distance_ts_id in day_points and day_points[self.distance_ts_id] :
            #         distance_points = self.replace_data_points(day, distance, day_points[self.distance_ts_id], self.distance_ts_id, "http://sociam.org/ontology/health/Distance") # subclass of http://purl.org/linked-data/cube#Observation
            #     else:
            #         distance_points = self.create_data_points(day, distance, self.distance_ts_id, "http://sociam.org/ontology/health/Distance") # subclass of http://purl.org/linked-data/cube#Observation
            #     # self.logger.debug("Saving {0} distance data points.".format(len(distance_points)))

            #     # processing floors
            #     floors = self.download_floors(day)
            #     floors_points = []
            #     if day_points and self.floors_ts_id in day_points and day_points[self.floors_ts_id] :
            #         floors_points = self.replace_data_points(day, floors, day_points[self.floors_ts_id], self.floors_ts_id, "http://sociam.org/ontology/health/FloorsClimbed") # subclass of http://purl.org/linked-data/cube#Observation
            #     else:
            #         floors_points = self.create_data_points(day, floors, self.floors_ts_id, "http://sociam.org/ontology/health/FloorsClimbed") # subclass of http://purl.org/linked-data/cube#Observation
            #     # self.logger.debug("Saving {0} floors data points.".format(len(floors_points)))

            #     # processing elevation
            #     elevation = self.download_elevation(day)
            #     elevation_points = []
            #     if day_points and self.elevation_ts_id in day_points and day_points[self.elevation_ts_id]:
            #         elevation_points = self.replace_data_points(day, elevation, day_points[self.elevation_ts_id], self.elevation_ts_id, "http://sociam.org/ontology/health/Elevation") # subclass of http://purl.org/linked-data/cube#Observation
            #     else:
            #         elevation_points = self.create_data_points(day, elevation, self.elevation_ts_id, "http://sociam.org/ontology/health/Elevation") # subclass of http://purl.org/linked-data/cube#Observation
            #     # self.logger.debug("Saving {0} elevation data points.".format(len(elevation_points)))
                
            #     proc_return_d = Deferred()
            #     def saved_cb(x):
            #         for (success, value) in x:
            #             if not success:
            #                 self.logger.error("Error saving data to INDX: {0}", value)
            #                 proc_return_d.errback(value)
            #         proc_return_d.callback(None)

            #     harvester["fetched_days"] = self.fetched_days
            #     harvester["zeros_from"] = self.all_zeros.isoformat()
            #     save_deferred = DeferredList([self.safe_update(indx, steps_points), self.safe_update(indx, calories_points), self.safe_update(indx, distance_points), self.safe_update(indx, floors_points), self.safe_update(indx, elevation_points), self.safe_update(indx, harvester)])
            #     save_deferred.addCallbacks(saved_cb, proc_return_d.errback)
            #     return proc_return_d

            # def advance_cb(x, day):
            #     self.logger.debug("Advance for day: {0}, {1}".format(day, (day < self.today())))
            #     if day < self.today():
            #         next_day = day + timedelta(days=+1)
            #         self.logger.debug("Advance next_day: {0}".format(next_day))
            #         get_day_points(day).addCallbacks(processing_cb, return_d.errback, callbackArgs=[day]).addCallbacks(advance_cb, return_d.errback, callbackArgs=[next_day])
            #     else:
            #         self.logger.debug("Finished harvesting round! Exiting harvest() .. ")
            #         return_d.callback(None)


    def create_data_points(self, day, data, ts_id, rdf_type=None):
        self.logger.debug("Started creating data points.")
        data_points = []
        for key in data.keys():
            if key.endswith('-intraday'):
                for point in data[key]["dataset"]:
                    interval_start = datetime.combine(day, datetime.strptime(point["time"], "%H:%M:%S").time()) 
                    interval_end = interval_start+timedelta(minutes=1) 
                    value = point["value"]
                    data_point = {  "@id": "fitbit_dp_{0}".format(uuid.uuid4()), 
                                    # "http://sociam.org/ontology/timeseries/start": interval_start.isoformat(),
                                    # "http://sociam.org/ontology/timeseries/end": interval_end.isoformat(),
                                    # "http://sociam.org/ontology/timeseries/value": value,
                                    # "http://purl.org/linked-data/cube#dataset": { "@id": ts_id } }
                                    "start": interval_start.isoformat(),
                                    "end": interval_end.isoformat(),
                                    "value": value,
                                    "timeseries": { "@id": ts_id } }
                    if rdf_type:
                        data_point["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"] = [ { "@id": rdf_type } ]
                    data_points.append(data_point)
                    # self.logger.debug("Created and appended data point: {0}".format(data_point))
        self.logger.debug("Finished creating data points.")
        return data_points

    def replace_data_points(self, day, new_data, old_data, ts_id, rdf_type=None):
        self.logger.debug("Started replacing values in data points.")
        data_points = []
        replaced = 0
        kept = 0
        created = 0
        for key in new_data.keys():
            if key.endswith('-intraday'):
                for point in new_data[key]["dataset"]:
                    data_point = None
                    interval_start = datetime.combine(day, datetime.strptime(point["time"], "%H:%M:%S").time()) 
                    interval_end = interval_start+timedelta(minutes=1) 
                    value = point["value"]
                    if interval_start in old_data:
                        if len(old_data[interval_start]) > 1 :
                            self.logger.error("There are {0} points for the same start time {1} in the same dataset {2}!!".format(len(old_data[interval_start]), interval_start, ts_id))
                        old_point = old_data[interval_start][0] # there shouldn't be more than 1 point here!!!
                        if old_point['value'][0]['@value'] == str(value):
                            kept = kept+1
                        else:
                            replaced = replaced+1
                            # if all_other_fields_match:
                            data_point = {  "@id": old_point['@id'] }
                    else:
                        created = created+1
                        data_point = {  "@id": "fitbit_dp_{0}".format(uuid.uuid4()) }
                    if data_point :
                        self.logger.debug("Making a data point for {0}".format(interval_start.isoformat()))
                        # data_point["http://sociam.org/ontology/timeseries/start"] = interval_start.isoformat()
                        # data_point["http://sociam.org/ontology/timeseries/end"] = interval_end.isoformat()
                        # data_point["http://sociam.org/ontology/timeseries/value"] = value
                        # data_point["http://purl.org/linked-data/cube#dataset"] = { "@id": ts_id } 
                        data_point["start"] = interval_start.isoformat()
                        data_point["end"] = interval_end.isoformat()
                        data_point["value"] = value
                        data_point["timeseries"] = { "@id": ts_id } 
                        if rdf_type:
                            data_point["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"] = [ { "@id": rdf_type } ]
                        data_points.append(data_point)
        self.logger.debug("Finished replacing values in data points - replaced: {0}, kept: {1}, created: {2}".format(replaced, kept, created))
        return data_points

    def download_steps(self, day):
        if (day == None):
            self.logger.error("No date given for download.")
            return []
        steps = self.fitbit_intraday.get_steps(day)[0]
        self.logger.debug("Retrieved steps data for {0}.".format(day.date()))
        return steps

    def download_calories(self, day):
        if (day == None):
            self.logger.error("No date given for download.")
            return []
        calories = self.fitbit_intraday.get_calories(day)[0]
        self.logger.debug("Retrieved calories data for {0}.".format(day.date()))
        return calories

    def download_distance(self, day):
        if (day == None):
            self.logger.error("No date given for download.")
            return []
        distance = self.fitbit_intraday.get_distance(day)[0]
        self.logger.debug("Retrieved distance data for {0}.".format(day.date()))
        return distance

    def download_floors(self, day):
        if (day == None):
            self.logger.error("No date given for download.")
            return []
        floors = self.fitbit_intraday.get_floors(day)[0]
        self.logger.debug("Retrieved floors data for {0}.".format(day.date()))
        return floors

    def download_elevation(self, day):
        if (day == None):
            self.logger.error("No date given for download.")
            return []
        elevation = self.fitbit_intraday.get_elevation(day)[0]
        self.logger.debug("Retrieved elevation data for {0}.".format(day.date()))
        return elevation

    def find_day_points(self, indx, day) :
        self.logger.debug("Find day data points from {0}".format(day.date().isoformat()))
        return_d = Deferred()

        def found_cb(results):
            out = {self.steps_ts_id:{}, self.calories_ts_id:{}, self.distance_ts_id:{}, self.floors_ts_id:{}, self.elevation_ts_id:{}}
            for (success, resp) in results:
                if success:
                    if resp and 'code' in resp and resp['code']==200 and 'data' in resp:
                        for pt in resp['data'] :
                            obj = resp['data'][pt]
                            # if 'http://purl.org/linked-data/cube#dataset' in obj and obj['http://purl.org/linked-data/cube#dataset'][0]['@id'] in [self.steps_ts_id, self.calories_ts_id, self.distance_ts_id, self.floors_ts_id, self.elevation_ts_id] :
                            #     objs_date_hash = out[obj['http://purl.org/linked-data/cube#dataset'][0]['@id']]
                            if 'timeseries' in obj and obj['timeseries'][0]['@id'] in [self.steps_ts_id, self.calories_ts_id, self.distance_ts_id, self.floors_ts_id, self.elevation_ts_id] :
                                objs_date_hash = out[obj['timeseries'][0]['@id']]
                                if find_start in objs_date_hash:
                                    objs_list = objs_date_hash[find_start]
                                else:
                                    objs_list = []
                                objs_list.append(obj) 
                                objs_date_hash[find_start] = objs_list
                                # out[obj['http://purl.org/linked-data/cube#dataset'][0]['@id']] = objs_date_hash
                                out[obj['timeseries'][0]['@id']] = objs_date_hash
                            self.logger.debug("Found points with start time {0}: {1}".format(find_start.isoformat(),objs_list))                    
                else:
                    self.logger.error("Didn't find any timepoints: {0}".format(resp))
            return_d.callback(out)

        deferreds = []
        for h in range(24):
            for m in range(60):
                find_start = datetime.combine(day.date(), time(h,m,0)) 
                self.logger.debug("Looking for data points with start time: {0}".format(find_start.isoformat()))
                deferreds.append(indx.query(json.dumps({"start":find_start.isoformat()})))
        DeferredList(deferreds).addCallbacks(found_cb, lambda f: self.logger.error("Error retrieving day points from indx for {0}: {1}".format(day.isoformat(), f)))
        
        return return_d

    def find_by_id(self, indx, oid) :
        return_d = Deferred()

        def find_cb(resp):
            self.logger.debug("find_by_id: received response: {0}".format(resp))
            if resp and "code" in resp and resp["code"] == 200 and "data" in resp:
                resp_data = resp["data"]
                if oid in resp_data:
                    self.logger.debug("Object {0} found!".format(oid))
                    return_d.callback(resp_data[oid])
                else:
                    self.logger.debug("Object {0} not found!".format(oid))
                    return_d.callback(None)
            else:
                self.logger.debug("Response code is not 200! respose: {0}".format(resp))
                return_d.errback(None) # put a useful error here!
        
        self.logger.debug("Searching object by id {0}".format(oid))
        indx.query(json.dumps({"@id": oid})).addCallbacks(find_cb, return_d.errback)
        return return_d

    def safe_update(self, indx, obj) :
        return_d = Deferred()
        self.logger.debug("Updating object {0} at box version {1}".format(obj, self.version))

        def update_cb(resp):
            self.logger.debug("safe_update: received response: {0}".format(resp))
            if resp and "code" in resp and "data" in resp:
                if resp["code"] == 201 or resp["code"] == 200:
                    self.version = resp["data"]["@version"]
                    self.logger.debug("Updated objects! new box version: {0}".format(self.version))
                    return_d.callback(self.version)

        def reupdate_cb(o):
            self.logger.debug("reupdate: received object: {0}".format(o))
            return_d.callback(o)

        def exception_cb(e):
            self.logger.error("EXCEPTION ? {0}".format(e))
            if isinstance(e.value, urllib2.HTTPError): # handle a version incorrect error, and update the version
                if e.value.code == 409: # 409 Obsolete
                    response = e.value.read()
                    json_response = json.loads(response)
                    self.version = json_response['@version']
                    self.safe_update(indx, obj).addCallbacks(reupdate_cb, return_d.errback) # try updating again now the version is correct
                else:
                    self.logger.error("HTTPError updating INDX: {0}".format(e.value))
                    # sys.exit(1)   
                    return_d.errback(e)
                pass
            else:
                self.logger.error("Error updating INDX: {0}".format(e.value))
                # sys.exit(1)   
                return_d.errback(e)

        indx.update(self.version, obj).addCallbacks(update_cb, exception_cb)
        return return_d

    def find_create(self, indx, oid, attrs={}):
        fc_d = Deferred()
        attrs.update({"@id":oid})

        def find_cb(obj, attrs=attrs):

            def create_cb(x, attrs=attrs):
                fc_d.callback(attrs)

            if obj is None:
                self.logger.debug("Object {0} not found! Creating it.".format(oid))
                self.safe_update(indx, attrs).addCallbacks(create_cb, fc_d.errback)
            else:
                fc_d.callback(obj)
        
        self.find_by_id(indx, oid).addCallbacks(find_cb, fc_d.errback)
        return fc_d

    def find_create_user(self, indx, fitbit_user):
        user_d = Deferred()

        def find_cb(obj, indx=indx, fitbit_user=fitbit_user):
            if obj is None:
                self.logger.debug("Fitbit user not found, storing it now.")
                self.user = fitbit_user["user"]
                self.user.update({"@id":self.user_id})
            else:
                self.user = obj
                self.user.update(fitbit_user["user"]) 
            self.safe_update(indx, self.user).addCallbacks(user_d.callback, user_d.errback)

        self.user_id = "fitbit_user_{0}".format(fitbit_user["user"]["encodedId"]) 
        self.find_by_id(indx, self.user_id).addCallbacks(find_cb, user_d.errback)
        return user_d

    def find_create_device(self, indx, fitbit_device):
        dev_d = Deferred()
        dev_id = "fitbit_device_{0}".format(fitbit_device["id"]) 

        def find_cb(obj, indx=indx, dev_id=dev_id, fitbit_device=fitbit_device):
            if obj is None:
                self.logger.debug("Fitbit device not found, storing it now.")
                obj = fitbit_device
                obj.update({"@id":dev_id})
            else:
                obj.update(fitbit_device) 
            self.devices.append(obj)
            self.safe_update(indx, obj).addCallbacks(dev_d.callback, dev_d.errback)

        self.find_by_id(indx, dev_id).addCallbacks(find_cb, dev_d.errback)
        return dev_d

    def today(self):
        return datetime.now().date()

if __name__ == '__main__':
    harvester = FitbitHarvester()
    harvester.run()

