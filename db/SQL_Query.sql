DROP TABLE IF EXISTS #FinalResult;
CREATE TABLE #FinalResult
(
    CreatedOn DATE,
    RegisterName NVARCHAR(255),
    [0%] DECIMAL(18,2),
    [6%] DECIMAL(18,2),
    [12%] DECIMAL(18,2),
    [21%] DECIMAL(18,2),
    [Bancontact] DECIMAL(18,2),
    [Cash] DECIMAL(18,2),
    [Betalen met kaart] DECIMAL(18,2),
    [UberEats] DECIMAL(18,2),
    [TakeAway] DECIMAL(18,2),
    [Deliveroo] DECIMAL(18,2),
    StoreId INT,
    StoreName NVARCHAR(255),
    StartDate DATE,
    EndDate DATE
);

DROP TABLE IF EXISTS #CashbookReport;
CREATE TABLE #CashbookReport
(
    Id INT,
    CreatedOn DATE DEFAULT GETDATE() NOT NULL,
    EntryDate DATE NOT NULL,
    Description NVARCHAR(128),
    Category NVARCHAR(64),
    Account INT,
    Vat DECIMAL(5, 2),
    Income MONEY NOT NULL,
    Expense MONEY NOT NULL,
    Total MONEY NOT NULL,
    RegisterName NVARCHAR(64),
    RegisterCode INT
);

DROP TABLE IF EXISTS #TempReport;
CREATE TABLE #TempReport
(
    CreatedOn DATE,
    RegisterName NVARCHAR(255),
    [0%] DECIMAL(18,2),
    [6%] DECIMAL(18,2),
    [12%] DECIMAL(18,2),
    [21%] DECIMAL(18,2),
    [Bancontact] DECIMAL(18,2),
    [Cash] DECIMAL(18,2),
    [Betalen met kaart] DECIMAL(18,2),
    [UberEats] DECIMAL(18,2),
    [TakeAway] DECIMAL(18,2),
    [Deliveroo] DECIMAL(18,2)
);

DROP TABLE IF EXISTS #DateRanges;
CREATE TABLE #DateRanges
(
    StartDate DATE,
    EndDate DATE
);

INSERT INTO #DateRanges (StartDate, EndDate)
VALUES
    (N'2025-04-01', N'2025-05-01'),
    (N'2025-05-01', N'2025-06-01'),
    (N'2025-06-01', N'2025-07-01');

DECLARE @startDate DATE, @endDate DATE;
DECLARE @storeId INT;
DECLARE @storeName NVARCHAR(255);

DECLARE store_cursor CURSOR
FOR
    SELECT
        S.Id, S.[Name]
    FROM dbo.[Store] as S
    WHERE S.[Name] NOT LIKE '%test%'
    ORDER BY S.[Name];

OPEN store_cursor;
FETCH NEXT FROM store_cursor INTO @storeId, @storeName;
WHILE @@FETCH_STATUS = 0
BEGIN
    DECLARE date_cursor CURSOR
    FOR
        SELECT
            StartDate,
            EndDate
        FROM #DateRanges;

    OPEN date_cursor;
    FETCH NEXT FROM date_cursor INTO @startDate, @endDate;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        TRUNCATE TABLE #CashbookReport;
    
        INSERT INTO #CashbookReport
        EXEC [dbo].[GetCashbookReport]
            @StartDate = @startDate,
            @EndDate = @endDate,
            @StoreId = @StoreId,
            @WorkdayTimeOffset = '00:00:00',
            @OnlyCashflow = 0;

        TRUNCATE TABLE #TempReport;

        /* #VATAccountingReportBelgium */
        begin
            DECLARE @OrderCompleted SMALLINT = 7;

            DROP TABLE IF EXISTS #PaymentMethodsSalesCompilations;
            CREATE TABLE #PaymentMethodsSalesCompilations
            (
                [CreatedOn] DATE,
                [PaymentMethodId] INT,
                [Name] NVARCHAR(64),
                [Sales] MONEY DEFAULT 0
            );

            INSERT INTO #PaymentMethodsSalesCompilations
            (
                [CreatedOn],
                [PaymentMethodId],
                [Name],
                [Sales]
            )
            SELECT
                CAST(o.[DateCreated] AS DATE) AS [CreatedOn],
                o.[PaymentMethodId],
                pm.[Name],
                SUM(o.[priceIncVat]) AS [Sales]
            FROM [Order] AS o
                JOIN [PaymentMethod] AS pm ON pm.[Id] = o.[PaymentMethodId]
            WHERE o.[OrderStatusEnum] = @OrderCompleted
                AND o.[StoreId] = @StoreId
                AND o.[DateCreated] >= @StartDate
                AND o.[DateCreated] <= @EndDate
            GROUP BY CAST(o.[DateCreated] AS DATE), o.[PaymentMethodId], pm.[Name];

            DROP TABLE IF EXISTS #PaymentMethodsOverview;
            CREATE TABLE #PaymentMethodsOverview
            (
                [CreatedOn] DATE,
                [Bancontact] MONEY,
                [Cash] MONEY,
                [Betalen met kaart] MONEY,
                [UberEats] MONEY,
                [TakeAway] MONEY,
                [Deliveroo] MONEY
            );

            INSERT INTO #PaymentMethodsOverview
            (
                [CreatedOn],
                [Bancontact],
                [Cash],
                [Betalen met kaart],
                [UberEats],
                [TakeAway],
                [Deliveroo]
            )
            SELECT
                [CreatedOn],
                SUM([Bancontact]) AS [Bancontact],
                SUM([Cash]) AS [Cash],
                SUM([Betalen met kaart]) AS [Betalen met kaart],
                SUM([UberEats]) AS [UberEats],
                SUM([TakeAway]) AS [TakeAway],
                SUM([Deliveroo]) AS [Deliveroo]
            FROM (
                SELECT *
                FROM #PaymentMethodsSalesCompilations
            ) AS pmsc
            PIVOT (
                SUM(pmsc.[Sales])
                FOR [Name] IN (
                    [Bancontact],
                    [Cash],
                    [Betalen met kaart],
                    [UberEats],
                    [TakeAway],
                    [Deliveroo]
                )
            ) AS piv3
            GROUP BY [CreatedOn];

            DROP TABLE IF EXISTS #VatOverview;
            CREATE TABLE #VatOverview
            (
                [CreatedOn] DATE,
                [RegisterName] NVARCHAR(128),
                [0%] MONEY,
                [6%] MONEY,
                [12%] MONEY,
                [21%] MONEY
            );
    
            INSERT INTO #VatOverview (
                [CreatedOn],
                [RegisterName],
                [0%],
                [6%],
                [12%],
                [21%]
            )
            SELECT
                [CreatedOn],
                [RegisterName],
                SUM([0%]) AS [0%],
                SUM([6%]) AS [6%],
                SUM([12%]) AS [12%],
                SUM([21%]) AS [21%]
            FROM (
                SELECT *
                FROM #CashbookReport AS cr
            ) AS cr
            PIVOT (
                SUM(cr.[Income])
                FOR [Description] IN (
                    [0%],
                    [6%],
                    [12%],
                    [21%]
                )
            ) AS piv2
            GROUP BY [CreatedOn],[RegisterName];

            DROP TABLE IF EXISTS #VATAccountingReport
            CREATE TABLE #VATAccountingReport
            (
                [CreatedOn] DATE,
                [RegisterName] NVARCHAR(128),
                [0%] MONEY,
                [6%] MONEY,
                [12%] MONEY,
                [21%] MONEY,
                [Bancontact] MONEY,
                [Cash] MONEY,
                [Betalen met kaart] MONEY,
                [UberEats] MONEY,
                [TakeAway] MONEY,
                [Deliveroo] MONEY
            );

            INSERT INTO #VATAccountingReport
            (
                [CreatedOn],
                [RegisterName],
                [0%],
                [6%],
                [12%],
                [21%],
                [Bancontact],
                [Cash],
                [Betalen met kaart],
                [UberEats],
                [TakeAway],
                [Deliveroo]
            )
            SELECT
                vat.[CreatedOn],
                vat.[RegisterName],
                isnull(vat.[0%],0),
                isnull(vat.[6%],0),
                isnull(vat.[12%],0),
                isnull(vat.[21%],0),
                isnull(pmo.[Bancontact],0),
                isnull(pmo.[Cash],0),
                isnull(pmo.[Betalen met kaart],0),
                isnull(pmo.[UberEats],0),
                isnull(pmo.[TakeAway],0),
                isnull(pmo.[Deliveroo],0)
            FROM #VatOverview AS vat
                LEFT JOIN #PaymentMethodsOverview AS pmo
                    ON pmo.[CreatedOn] = vat.[CreatedOn]
            ORDER BY vat.[CreatedOn] ASC;

            insert into #TempReport (
                CreatedOn,
                RegisterName,
                [0%],
                [6%],
                [12%],
                [21%],
                [Bancontact],
                [Cash],
                [Betalen met kaart],
                [UberEats],
                [TakeAway],
                [Deliveroo]
            )
            SELECT
                vatar.[CreatedOn],
                vatar.[RegisterName],
                vatar.[0%],
                vatar.[6%],
                vatar.[12%],
                vatar.[21%],
                vatar.[Bancontact],
                vatar.[Cash],
                vatar.[Betalen met kaart],
                vatar.[UberEats],
                vatar.[TakeAway],
                vatar.[Deliveroo]
            FROM #VATAccountingReport AS vatar;
        end

        INSERT INTO #FinalResult (
            CreatedOn, RegisterName, [0%], [6%], [12%], [21%],
            [Bancontact], [Cash], [Betalen met kaart],
            [UberEats], [TakeAway], [Deliveroo],
            StoreId, StoreName, StartDate, EndDate
        )
        SELECT
            CreatedOn, RegisterName, [0%], [6%], [12%], [21%],
            [Bancontact], [Cash], [Betalen met kaart],
            [UberEats], [TakeAway], [Deliveroo],
            @storeId, @storeName, @startDate, @endDate
        FROM #TempReport;
        
        FETCH NEXT FROM date_cursor INTO @startDate, @endDate;
    END
    
    CLOSE date_cursor;
    DEALLOCATE date_cursor;
    
    FETCH NEXT FROM store_cursor INTO @storeId, @storeName;
END

CLOSE store_cursor;
DEALLOCATE store_cursor;

SELECT
    CreatedOn,
    StoreId,
    RegisterName = StoreName,
    [0%],
    [6%],
    [12%],
    [21%],
    [Bancontact],
    [Cash],
    [Betalen met kaart],
    [UberEats],
    [TakeAway],
    [Deliveroo]
FROM #FinalResult
ORDER BY StoreName, CreatedOn;