import pandas as pd
from typing import List

from google.analytics.admin_v1beta import ListConversionEventsRequest, ConversionEvent, CreateConversionEventRequest, \
    UpdateConversionEventRequest, DeleteConversionEventRequest
from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
from mindsdb_sql_parser import Constant
from mindsdb_sql_parser import ast
from mindsdb.integrations.libs.api_handler import APITable
from mindsdb.integrations.utilities.sql_utils import extract_comparison_conditions


def get_all_identifiers(node) -> List[str]:
    """Recursively extract all identifier names from an AST node or list of nodes."""
    ids = []
    if isinstance(node, ast.Identifier):
        ids.append(node.parts[-1])
    elif isinstance(node, (ast.Function, ast.BinaryOperation, ast.UnaryOperation)):
        if hasattr(node, 'args') and node.args:
            for arg in node.args:
                ids.extend(get_all_identifiers(arg))
    elif isinstance(node, ast.TypeCast):
        ids.extend(get_all_identifiers(node.arg))
    elif isinstance(node, list):
        for item in node:
            ids.extend(get_all_identifiers(item))
    return ids

# All standard dimensions from GA4 Data API Core Reporting schema
# https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema
ALL_DIMENSIONS = [
    # Time
    'date', 'dateHour', 'dateHourMinute', 'dayOfWeek', 'day', 'week', 'month', 'year',
    'hour', 'minute', 'nthDay', 'nthHour', 'nthMinute', 'nthMonth', 'nthWeek', 'nthYear',
    # Geography
    'country', 'countryId', 'continent', 'continentId', 'subContinent', 'region',
    'city', 'cityId', 'latitude', 'longitude', 'metro',
    # Page / Content
    'pagePath', 'pageTitle', 'pageReferrer', 'pagePathPlusQueryString',
    'fullPageUrl', 'landingPage', 'landingPagePlusQueryString',
    'contentGroup', 'contentId', 'contentType',
    # Traffic Source
    'sessionSource', 'sessionMedium', 'sessionCampaignName', 'sessionCampaignId',
    'sessionDefaultChannelGroup', 'sessionGoogleAdsAccountName', 'sessionGoogleAdsCampaignId',
    'sessionGoogleAdsCampaignName', 'sessionGoogleAdsCampaignType', 'sessionGoogleAdsAdGroupId',
    'sessionGoogleAdsAdGroupName', 'sessionGoogleAdsKeyword', 'sessionGoogleAdsMatchType',
    'sessionGoogleAdsNetworkType', 'sessionGoogleAdsQuery',
    'sessionManualAdContent', 'sessionManualTerm', 'sessionSa360AdGroupName',
    'sessionSa360CampaignId', 'sessionSa360CampaignName', 'sessionSa360CreativeFormat',
    'sessionSa360EngineAccountId', 'sessionSa360EngineAccountName', 'sessionSa360EngineAccountType',
    'sessionSa360Keyword', 'sessionSa360Medium', 'sessionSa360Query', 'sessionSa360Source',
    'sessionSourceMedium', 'sessionSourcePlatform',
    'firstUserSource', 'firstUserMedium', 'firstUserCampaignName', 'firstUserCampaignId',
    'firstUserDefaultChannelGroup', 'firstUserGoogleAdsCampaignName',
    'firstUserGoogleAdsCampaignType', 'firstUserSourceMedium', 'firstUserSourcePlatform',
    'firstUserManualAdContent', 'firstUserManualTerm',
    'source', 'medium', 'campaignName', 'campaignId', 'defaultChannelGroup',
    'sourceMedium', 'sourcePlatform',
    # Device
    'deviceCategory', 'mobileDeviceBranding', 'mobileDeviceModel', 'mobileDeviceMarketingName',
    'mobileInputSelector', 'mobileDeviceInfo', 'operatingSystem', 'operatingSystemVersion',
    'operatingSystemWithVersion', 'browser', 'browserVersion', 'screenResolution',
    'language', 'languageCode',
    # User
    'newVsReturning', 'userAgeBracket', 'userGender',
    'signedInWithUserId', 'isConversionEvent',
    # App / Platform
    'platform', 'platformDeviceCategory', 'appVersion', 'appInstallerId',
    'appStore', 'appName', 'streamId', 'streamName',
    # Event
    'eventName', 'customEvent:parameter_name',
    # Search Console
    'googleAdsAccountName', 'googleAdsCampaignId', 'googleAdsCampaignName',
    'googleAdsCampaignType', 'googleAdsAdGroupId', 'googleAdsAdGroupName',
    'googleAdsKeyword', 'googleAdsQuery',
    # Organic Search
    'searchTerm', 'organicGoogleSearchQuery', 'organicGoogleSearchCategory',
    'organicGoogleSearchViewportSize',
    # Ecommerce
    'itemId', 'itemName', 'itemBrand', 'itemCategory', 'itemCategory2', 'itemCategory3',
    'itemCategory4', 'itemCategory5', 'itemListId', 'itemListName', 'itemListPosition',
    'itemLocationId', 'itemPromotionId', 'itemPromotionName', 'itemPromotionCreativeName',
    'orderCoupon', 'transactionId', 'shippingTier', 'paymentType',
    'adFormat', 'adSourceName', 'adUnitName',
    # Audience / Cohort
    'audienceId', 'audienceName', 'cohort', 'cohortNthDay', 'cohortNthWeek', 'cohortNthMonth',
    # Other
    'achievementId', 'character', 'brandingInterest', 'level', 'virtual_currency_name',
    'groupId', 'fileExtension', 'fileName', 'linkClasses', 'linkDomain',
    'linkId', 'linkText', 'linkUrl', 'method', 'outbound', 'percentScrolled',
    'searchTerm', 'videoProvider', 'videoTitle', 'videoUrl', 'visible',
    'testDataFilterName', 'unifiedPagePathScreen', 'unifiedPageScreen',
    'unifiedScreenClass', 'unifiedScreenName',
]

# All standard metrics from GA4 Data API Core Reporting schema
# https://developers.google.com/analytics/devguides/reporting/data/v1/api-schema
ALL_METRICS = [
    # Users
    'activeUsers', 'newUsers', 'totalUsers', 'active1DayUsers', 'active7DayUsers',
    'active28DayUsers', 'dauPerMau', 'dauPerWau', 'wauPerMau',
    'firstTimePurchasers', 'firstTimePurchasersRate',
    # Sessions
    'sessions', 'sessionsPerUser', 'bounceRate', 'engagementRate',
    'engagedSessions', 'averageSessionDuration', 'userEngagementDuration',
    # Page / Screen
    'screenPageViews', 'screenPageViewsPerSession', 'screenPageViewsPerUser',
    # Events
    'eventCount', 'eventCountPerUser', 'eventsPerSession',
    # Conversions / Key Events
    'conversions', 'sessionConversionRate', 'userConversionRate',
    'keyEvents', 'keyEventRate',
    # Engagement
    'scrolledUsers',
    # Revenue
    'totalRevenue', 'purchaseRevenue', 'advertiserAdRevenue',
    'publisherAdRevenue', 'subscriptionRevenue',
    # Ecommerce
    'ecommercePurchases', 'addToCarts', 'checkouts', 'cartToViewRate',
    'purchaseToViewRate', 'itemViews', 'itemListViews', 'itemListClicks',
    'itemListClickThroughRate', 'itemsAddedToCart', 'itemsCheckedOut',
    'itemsPurchased', 'itemsViewed', 'itemRevenue', 'itemDiscountAmount',
    'itemPromotionClicks', 'itemPromotionViews', 'itemPromotionClickThroughRate',
    'refundAmount', 'shippingAmount', 'taxAmount', 'transactions',
    'transactionsPerPurchaser', 'averagePurchaseRevenue', 'averagePurchaseRevenuePerPayingUser',
    'averagePurchaseRevenuePerUser', 'averageRevenuePerUser',
    # Advertising
    'publisherAdClicks', 'publisherAdImpressions', 'adUnitExposure',
    # Organic Search
    'organicGoogleSearchClicks', 'organicGoogleSearchImpressions',
    'organicGoogleSearchClickThroughRate', 'organicGoogleSearchAveragePosition',
    # Video
    'videoViews', 'videoCompletions',
    # Crashes (App)
    'crashAffectedUsers', 'crashFreeUsersRate',
    # Other
    'totalAdRevenue',
]

# Default fallback for SELECT * — most commonly asked metrics, capped at 10 each
DEFAULT_DIMENSIONS = ['date', 'pagePath', 'sessionSource', 'country', 'deviceCategory']
DEFAULT_METRICS = [
    'sessions', 'activeUsers', 'newUsers', 'screenPageViews',
    'bounceRate', 'averageSessionDuration', 'engagementRate', 'totalRevenue',
    'conversions', 'eventCount',
]


class ConversionEventsTable(APITable):

    def select(self, query: ast.Select) -> pd.DataFrame:
        """
        Gets all conversion events from google analytics property.

        Args:
            query (ast.Select): SQL query to parse.

        Returns:
            Response: Response object containing the results.
        """
        # Parse the query to get the conditions.
        conditions = extract_comparison_conditions(query.where)
        # Get the page size from the conditions.
        params = {}
        for op, arg1, arg2 in conditions:
            if arg1 == 'page_size':
                params[arg1] = arg2
            else:
                raise NotImplementedError

        # Get the order by from the query.
        if query.order_by is not None:
            pass

        if query.limit is not None:
            pass

        # Get the conversion events from the Google Analytics Admin API.
        conversion_events = pd.DataFrame(columns=self.get_columns())
        result = self.get_conversion_events(params=params)
        conversion_events_data = self.extract_conversion_events_data(result)
        events = self.concat_dataframes(conversion_events, conversion_events_data)

        selected_columns = []
        for target in query.targets:
            if isinstance(target, ast.Star):
                selected_columns = self.get_columns()
                break
            selected_columns.extend(get_all_identifiers(target))

        if len(events) == 0:
            events = pd.DataFrame([], columns=selected_columns)
        else:
            events.columns = self.get_columns()
            for col in set(events.columns).difference(set(selected_columns)):
                events = events.drop(col, axis=1)
        return events

    def insert(self, query: ast.Insert):
        """
        Inserts a conversion event into your GA4 property.

        Args:
            query (ast.Insert): SQL query to parse.
        """
        columns = [col.name for col in query.columns]

        supported_columns = {'event_name', 'countingMethod'}
        if not set(columns).issubset(supported_columns):
            unsupported_columns = set(columns).difference(supported_columns)
            raise ValueError(
                "Unsupported columns for create conversion event: "
                + ", ".join(unsupported_columns)
            )
        params = {}

        for row in query.values:
            params = dict(zip(columns, row))

        # get params values of a type <Constant>
        if isinstance(params['countingMethod'], str):
            params['countingMethod'] = int(params['countingMethod'])
        elif isinstance(params['countingMethod'], Constant):
            params['countingMethod'] = params['countingMethod'].value
        else:
            params['countingMethod'] = params['countingMethod']

        if isinstance(params['event_name'], Constant):
            params['event_name'] = params['event_name'].value
        else:
            params['event_name'] = params['event_name']

        # Insert the conversion event into the Google Analytics Admin API.
        conversion_events = pd.DataFrame(columns=self.get_columns())
        result = self.create_conversion_event(params=params)
        conversion_events_data = self.extract_conversion_events_data([result])
        self.concat_dataframes(conversion_events, conversion_events_data)

    def update(self, query: ast.Update):
        """
        Updates a conversion event into your GA4 property.

        Args:
            query (ast.Update): SQL query to parse.
        """
        # Get the values from the query.
        values = query.update_columns.items()
        data_list = list(values)
        # Get the conversion event data from the values.
        params = {}
        for col, val in zip(query.update_columns, data_list):
            params[col] = val

        conditions = extract_comparison_conditions(query.where)
        for op, arg1, arg2 in conditions:
            if arg1 == 'name':
                if op == '=':
                    params['name'] = arg2
                else:
                    raise NotImplementedError
            else:
                raise NotImplementedError

        # get params values of a type <Constant>
        params['countingMethod'] = params['countingMethod'][1].value

        # Update the conversion event in the Google Analytics Admin API.
        conversion_events = pd.DataFrame(columns=self.get_columns())
        result = self.update_conversion_event(params=params)
        conversion_events_data = self.extract_conversion_events_data([result])
        self.concat_dataframes(conversion_events, conversion_events_data)

    def delete(self, query: ast.Delete):
        """
        Deletes a conversion event into your GA4 property.

        Args:
            query (ast.Delete): SQL query to parse.
        """

        # Parse the query to get the conditions.
        conditions = extract_comparison_conditions(query.where)
        for op, arg1, arg2 in conditions:
            if op == 'or':
                raise NotImplementedError('OR is not supported')
            if arg1 == 'name':
                if op == '=':
                    self.delete_conversion_event(params={'name': arg2})
                else:
                    raise NotImplementedError(f'Unknown op: {op}')
            else:
                raise NotImplementedError(f'Unknown clause: {arg1}')

    def get_conversion_events(self, params: dict = None):
        """
        List all conversion events in your GA4 property
        Args:
            params (dict): query parameters
        Returns:
            ConversionEvent objects
        """
        service = self.handler.connect()
        page_token = None
        url = self.handler.get_api_url('properties')
        all_results = []

        while True:
            request = ListConversionEventsRequest(
                parent=url, page_token=page_token, **params
            )
            result = service.list_conversion_events(request)
            all_results.extend(result.conversion_events)
            page_token = result.next_page_token
            if not page_token:
                break

        return all_results

    def create_conversion_event(self, params: dict = None):
        """
        Create a conversion event in your property.
        Args:
            params (dict): query parameters
        Returns:
            ConversionEvent object
        """
        service = self.handler.connect()
        url = self.handler.get_api_url('properties')

        conversion_event = ConversionEvent(
            event_name=params['event_name'],
            counting_method=params['countingMethod']
        )
        request = CreateConversionEventRequest(conversion_event=conversion_event,
                                               parent=url)
        result = service.create_conversion_event(request)

        return result

    def update_conversion_event(self, params: dict = None):
        """
        Update a conversion event in your property.
        Args:
            params (dict): query parameters
        Returns:
            ConversionEvent object
        """
        service = self.handler.connect()

        conversion_event = ConversionEvent(
            name=params['name'],
            counting_method=params['countingMethod']
        )
        request = UpdateConversionEventRequest(conversion_event=conversion_event,
                                               update_mask='*')
        result = service.update_conversion_event(request)

        return result

    def delete_conversion_event(self, params: dict = None):
        """
        Delete a conversion event in your property.
        Args:
            params (dict): query parameters
        """
        service = self.handler.connect()
        request = DeleteConversionEventRequest(name=params['name'])
        service.delete_conversion_event(request)

    @staticmethod
    def extract_conversion_events_data(conversion_events):
        """
        Extract conversion events data and return a list of lists.
        Args:
            conversion_events: List of ConversionEvent objects
        Returns:
            List of lists containing conversion event data
        """
        conversion_events_data = []
        for conversion_event in conversion_events:
            data_row = [
                conversion_event.name,
                conversion_event.event_name,
                conversion_event.create_time,
                conversion_event.deletable,
                conversion_event.custom,
                conversion_event.ConversionCountingMethod(conversion_event.counting_method).name,
            ]
            conversion_events_data.append(data_row)
        return conversion_events_data

    def concat_dataframes(self, existing_df, data):
        """
        Concatenate existing DataFrame with new data.
        Args:
            existing_df: Existing DataFrame
            data: New data to be added to the DataFrame
        Returns:
            Concatenated DataFrame
        """
        return pd.concat(
            [existing_df, pd.DataFrame(data, columns=self.get_columns())],
            ignore_index=True
        )

    def get_columns(self) -> List[str]:
        """
        Gets all columns to be returned in pandas DataFrame responses

        Returns:
        List[str]: List of columns
        """
        return [
            'name',
            'event_name',
            'create_time',
            'deletable',
            'custom',
            'countingMethod',
        ]


class ReportTable(APITable):

    def select(self, query: ast.Select) -> pd.DataFrame:
        """
        Runs a report against the GA4 Data API.

        The agent should SELECT only the specific columns it needs. The API supports
        a maximum of 10 dimensions and 10 metrics per request. Selecting specific
        columns ensures the API call stays within this limit.

        Available dimensions:
            date, pagePath, sessionSource, sessionMedium, sessionCampaignName,
            country, city, deviceCategory, operatingSystem, browser, language,
            eventName, pageTitle

        Available metrics:
            sessions, activeUsers, newUsers, totalUsers, screenPageViews,
            bounceRate, averageSessionDuration, engagementRate, engagedSessions,
            eventCount, conversions, totalRevenue, ecommercePurchases,
            addToCarts, checkouts, sessionConversionRate, userEngagementDuration,
            scrolledUsers

        Supported WHERE conditions:
            - start_date: Accepts GA4 relative values ('NdaysAgo', 'yesterday', 'today')
              or absolute dates in 'YYYY-MM-DD' format. Default: '30daysAgo'.
            - end_date: Same format as start_date. Default: 'today'.

        Example queries:
            SELECT date, sessions, activeUsers FROM report WHERE start_date = '7daysAgo'
            SELECT country, sessions, totalRevenue FROM report WHERE start_date = '2024-01-01' AND end_date = '2024-03-31'

        Args:
            query (ast.Select): SQL query to parse.

        Returns:
            pd.DataFrame
        """
        conditions = extract_comparison_conditions(query.where)
        params = {
            'start_date': '30daysAgo',
            'end_date': 'today',
        }
        for op, arg1, arg2 in conditions:
            if arg1 in ('start_date', 'end_date'):
                params[arg1] = arg2
            else:
                raise NotImplementedError

        if query.order_by is not None:
            pass

        if query.limit is not None:
            pass

        # Determine which columns the agent selected
        requested_columns = []
        is_star = False
        for target in query.targets:
            if isinstance(target, ast.Star):
                is_star = True
                break
            requested_columns.extend(get_all_identifiers(target))

        if is_star:
            selected_dimensions = DEFAULT_DIMENSIONS
            selected_metrics = DEFAULT_METRICS
        else:
            selected_dimensions = [c for c in requested_columns if c in ALL_DIMENSIONS]
            selected_metrics = [c for c in requested_columns if c in ALL_METRICS]

            if not selected_dimensions:
                selected_dimensions = ['date']

            selected_dimensions = selected_dimensions[:10]
            selected_metrics = selected_metrics[:10]

        service = self.handler.connect_data_api()
        request = RunReportRequest(
            property=f"properties/{self.handler.property_id}",
            date_ranges=[DateRange(start_date=params['start_date'], end_date=params['end_date'])],
            dimensions=[Dimension(name=d) for d in selected_dimensions],
            metrics=[Metric(name=m) for m in selected_metrics],
        )
        response = service.run_report(request)

        rows = []
        for row in response.rows:
            rows.append(
                [d.value for d in row.dimension_values] +
                [m.value for m in row.metric_values]
            )

        return pd.DataFrame(rows, columns=selected_dimensions + selected_metrics)

    def get_columns(self) -> List[str]:
        """
        Gets all columns to be returned in pandas DataFrame responses.
        The agent uses this schema to know which columns exist and select only what it needs.
        Max 10 dimensions and 10 metrics can be requested per API call.

        Returns:
        List[str]: List of columns
        """
        return ALL_DIMENSIONS + ALL_METRICS