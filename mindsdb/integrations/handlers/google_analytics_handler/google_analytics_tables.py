import pandas as pd
from typing import List, Optional

from google.analytics.admin_v1beta import ListConversionEventsRequest, ConversionEvent, CreateConversionEventRequest, \
    UpdateConversionEventRequest, DeleteConversionEventRequest
from google.analytics.data_v1beta.types import (
    RunReportRequest, Dimension, Metric, DateRange,
    FilterExpression, FilterExpressionList, Filter,
)
from mindsdb_sql_parser import Constant
from mindsdb_sql_parser import ast
from mindsdb.integrations.libs.api_handler import APITable
from mindsdb.integrations.utilities.sql_utils import extract_comparison_conditions
from mindsdb.utilities import log
logger = log.getLogger(__name__)


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

_OP_MAP = {
    '=':    lambda col, val: col == val,
    '!=':   lambda col, val: col != val,
    '>':    lambda col, val: col > val,
    '<':    lambda col, val: col < val,
    '>=':   lambda col, val: col >= val,
    '<=':   lambda col, val: col <= val,
    'LIKE': lambda col, val: col.str.contains(val.replace('%', ''), na=False, case=False),
}

def _build_server_side_dimension_filter(
    dimension_filters: list,
) -> Optional[FilterExpression]:
    """
    Convert a list of (op, column, value) triples into a GA4 FilterExpression
    that is pushed to the API, reducing data transfer and honouring row limits.

    Only exact-match (=) and LIKE/contains patterns are translated server-side.
    Inequality operators (!=, >, <, >=, <=) fall back to post-fetch filtering
    because GA4 DimensionFilter does not support numeric range on string fields.

    Returns None if no server-side-translatable filters exist.
    """
    if not dimension_filters:
        return None

    clauses: List[FilterExpression] = []
    for op, col, val in dimension_filters:
        if op == '=':
            clauses.append(FilterExpression(
                filter=Filter(
                    field_name=col,
                    string_filter=Filter.StringFilter(
                        value=val,
                        match_type=Filter.StringFilter.MatchType.EXACT,
                        case_sensitive=False,
                    ),
                )
            ))
        elif op == 'LIKE':
            pattern = val.replace('%', '').replace('_', '')
            clauses.append(FilterExpression(
                filter=Filter(
                    field_name=col,
                    string_filter=Filter.StringFilter(
                        value=pattern,
                        match_type=Filter.StringFilter.MatchType.CONTAINS,
                        case_sensitive=False,
                    ),
                )
            ))

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return FilterExpression(
        and_group=FilterExpressionList(expressions=clauses)
    )


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
        new_df = pd.DataFrame(data, columns=self.get_columns())
        frames = [f for f in [existing_df, new_df] if not f.empty]
        if not frames:
            return pd.DataFrame(columns=self.get_columns())
        return pd.concat(frames, ignore_index=True)

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

        Execution flow:
        1. Schema probe (LIMIT 0): return empty DataFrame with ALL column names
           so MindsDB learns the full schema without a GA API call.
        2. Real query: parse requested columns from SELECT, WHERE, GROUP BY,
           HAVING — make one GA API call with precisely those columns.

        NOTE: MindsDB's APIHandler.query() base class unconditionally replaces
        query.targets with [Star()] before calling select().  We recover the
        intended columns from the WHERE clause (dimension keys + date params)
        and fall back to a sensible default when none can be inferred.

        Args:
            query (ast.Select): SQL query to parse.

        Returns:
            pd.DataFrame
        """
        logger.debug(
            "GA select() called | targets=%s | where=%s | group_by=%s | having=%s | limit=%s",
            query.targets, query.where, query.group_by, query.having, query.limit,
        )

        is_limit_zero = query.limit is not None and query.limit.value == 0
        is_empty_targets = not query.targets

        targets_are_star = bool(query.targets) and all(
            isinstance(t, ast.Star) for t in query.targets
        )

        conditions = []
        if query.where is not None:
            try:
                conditions = extract_comparison_conditions(query.where)
            except NotImplementedError:
                logger.warning("GA select(): could not fully parse WHERE clause — proceeding with partial conditions")

        has_date_filter = any(
            arg1 in ('start_date', 'end_date') for _, arg1, _ in conditions
        )

        if is_limit_zero or is_empty_targets or (targets_are_star and not has_date_filter):
            logger.debug("GA select(): schema probe detected — returning empty schema DataFrame")
            return pd.DataFrame(columns=ALL_DIMENSIONS + ALL_METRICS)

        params = {'start_date': '30daysAgo', 'end_date': 'today'}
        dimension_filters: list = []  # (op, column, value)

        for op, arg1, arg2 in conditions:
            if arg1 in ('start_date', 'end_date'):
                params[arg1] = str(arg2)
            elif arg1 in ALL_DIMENSIONS:
                dimension_filters.append((op, arg1, str(arg2)))

        logger.debug("GA select(): date_range=%s  dimension_filters=%s", params, dimension_filters)

        if query.having is not None:
            try:
                having_conditions = extract_comparison_conditions(query.having)
                for op, arg1, arg2 in having_conditions:
                    if arg1 in ALL_DIMENSIONS:
                        dimension_filters.append((op, arg1, str(arg2)))
            except NotImplementedError:
                pass

        requested_columns: list = []

        if not targets_are_star:
            for target in query.targets:
                requested_columns.extend(get_all_identifiers(target))

        if query.group_by:
            for group_col in query.group_by:
                for col in get_all_identifiers(group_col):
                    if col not in requested_columns:
                        requested_columns.append(col)

        # Always include dimension-filter columns so we can apply post-filtering
        for _, col, _ in dimension_filters:
            if col not in requested_columns:
                requested_columns.append(col)

        logger.debug("GA select(): requested_columns before classification=%s", requested_columns)

        selected_dimensions = [c for c in requested_columns if c in ALL_DIMENSIONS]
        selected_metrics    = [c for c in requested_columns if c in ALL_METRICS]

        
        if not selected_metrics:
            raise ValueError(
                f"No valid GA4 metrics found in query. "
                f"Columns seen: {requested_columns}. "
                f"Check ALL_METRICS for valid metric names."
            )
        # Only raise for missing dimensions if the query also has no metrics to return
        if not selected_dimensions:
            logger.debug(
                "GA select(): no dimensions requested — running aggregate (dimension-less) query"
            )

        logger.debug("GA select(): dimensions=%s  metrics=%s", selected_dimensions, selected_metrics)

        if len(selected_dimensions) > 10:
            raise ValueError(
                f"Too many dimensions requested ({len(selected_dimensions)}). "
                f"GA4 API allows max 10 per query."
            )

        row_limit = 10_000
        if query.limit is not None and query.limit.value > 0:
            row_limit = int(query.limit.value)
        logger.debug("GA select(): row_limit=%s", row_limit)
        server_filter = _build_server_side_dimension_filter(dimension_filters)
        logger.debug("GA select(): server_side_filter=%s", server_filter)
        service    = self.handler.connect_data_api()
        date_range = DateRange(start_date=params['start_date'], end_date=params['end_date'])

        def run_ga_request(dimensions, metrics):
            """Make one GA4 RunReport call and return a DataFrame."""
            req = RunReportRequest(
                property=f"properties/{self.handler.property_id}",
                date_ranges=[date_range],
                dimensions=[Dimension(name=d) for d in dimensions],
                metrics=[Metric(name=m) for m in metrics],
                limit=row_limit,
                dimension_filter=server_filter,
            )
            logger.debug(
                "GA RunReportRequest | property=%s | dates=%s→%s | dims=%s | metrics=%s | limit=%s",
                self.handler.property_id,
                params['start_date'], params['end_date'],
                dimensions, metrics, row_limit,
            )
            resp = service.run_report(req)
            logger.debug(
                "GA RunReport response | row_count=%s | rows_returned=%s",
                resp.row_count, len(resp.rows),
            )
            rows = [
                [d.value for d in row.dimension_values] +
                [m.value for m in row.metric_values]
                for row in resp.rows
            ]
            return pd.DataFrame(rows, columns=dimensions + metrics)

        # Split metrics into batches of ≤10 (GA4 API limit), merge results
        metric_batches = [
            selected_metrics[i:i + 10]
            for i in range(0, max(len(selected_metrics), 1), 10)
        ]
        df = run_ga_request(selected_dimensions, metric_batches[0])
        for batch in metric_batches[1:]:
            df_batch = run_ga_request(selected_dimensions, batch)
            if selected_dimensions:
                df = pd.merge(df, df_batch, on=selected_dimensions, how='inner')
            else:
                df = pd.concat([df, df_batch], axis=1)

        # ── Apply post-fetch dimension filters ────────────────────────────────
        for op, col, val in dimension_filters:
            if col not in df.columns:
                logger.warning(
                    "GA select(): dimension filter column '%s' not in result — skipping post-filter", col
                )
                continue
            filter_fn = _OP_MAP.get(op)
            if not filter_fn:
                logger.warning("GA select(): unsupported filter operator '%s' — skipping", op)
                continue
            df = df[filter_fn(df[col], val)]

        logger.debug("GA select(): returning %d rows with columns %s", len(df), list(df.columns))
        return df

    def list(self, *args, **kwargs) -> pd.DataFrame:
        raise NotImplementedError(
            "ReportTable does not support list(); use select() directly."
        )

    def get_columns(self) -> List[str]:
        """
        Full schema exposed to MindsDB for agent/catalog discovery.
        Max 10 dimensions + 10 metrics can be requested per GA API call,
        but all valid names are listed here for the agent to reference.
        """
        return ALL_DIMENSIONS + ALL_METRICS