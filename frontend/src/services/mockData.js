/**
 * COMPREHENSIVE ENTERPRISE MOCK DATA FOR OPENMETADATA EXPERIENCE
 * Covers: Full Schema, Profiler Histograms, End-to-End Lineage, Impact Analysis,
 * Observability SLAs, PII Masking, Activity Feeds & Tasks, Tiering & Governance
 */

export const HEALTHCARE_TABLE_DESCRIPTIONS = {
  patients: "Bảng hồ sơ định danh và thông tin nhân khẩu học/lâm sàng của bệnh nhân (họ tên, ngày sinh, ngày tử vong, số an sinh xã hội SSN, địa chỉ và tổng chi phí khám chữa bệnh tích lũy).",
  encounters: "Bảng lịch sử các đợt khám bệnh, cấp cứu, khám định kỳ và điều trị nội trú/ngoại trú của bệnh nhân tại các cơ sở y tế (thời gian tiếp nhận, lý do khám, khoa phòng điều trị).",
  claims: "Bảng hồ sơ yêu cầu chi trả và bồi thường viện phí từ bảo hiểm y tế hoặc đơn vị bảo trợ (tổng số tiền yêu cầu bồi thường, số tiền được bảo hiểm chi trả, tình trạng phê duyệt đơn).",
  claims_transactions: "Bảng chi tiết các giao dịch tài chính, thanh toán viện phí từng đợt và các khoản khấu trừ trực tiếp theo từng hồ sơ yêu cầu bồi thường bảo hiểm.",
  conditions: "Bảng ghi nhận các bệnh lý, chẩn đoán xác định, tiền sử bệnh và tình trạng sức khỏe hiện tại của bệnh nhân theo chuẩn phân loại bệnh tật quốc tế ICD-10 và SNOMED-CT.",
  medications: "Bảng danh mục đơn thuốc, lịch trình cấp phát thuốc, liều dùng, đường dùng và hướng dẫn điều trị bằng dược phẩm cho bệnh nhân.",
  allergies: "Bảng theo dõi tiền sử dị ứng thuốc, dị ứng thức ăn và các tác nhân môi trường của bệnh nhân, phân loại mức độ nghiêm trọng và phản ứng lâm sàng tương ứng.",
  careplans: "Bảng phác đồ điều trị, kế hoạch chăm sóc dài hạn và các mục tiêu can thiệp y tế đối với các bệnh mãn tính hoặc phục hồi chức năng sau phẫu thuật.",
  procedures: "Bảng ghi nhận các thủ thuật y tế, phẫu thuật can thiệp, xét nghiệm chuyên sâu và chẩn đoán chức năng đã thực hiện trên bệnh nhân.",
  observations: "Bảng lưu trữ các chỉ số sinh hiệu (huyết áp, nhịp tim, thân nhiệt, chỉ số BMI, SpO2) và kết quả xét nghiệm định lượng/định tính trong phòng thí nghiệm y khoa.",
  immunizations: "Bảng quản lý lịch sử tiêm chủng vắc-xin phòng ngừa của bệnh nhân (tên loại vắc-xin, ngày tiêm, liều lượng, trạng thái tiêm và khuyến cáo tái chủng).",
  devices: "Bảng quản lý các thiết bị y tế cấy ghép, máy tạo nhịp tim, nẹp cố định hoặc thiết bị hỗ trợ điều trị được gắn cho bệnh nhân.",
  imaging_studies: "Bảng theo dõi các ca chẩn đoán hình ảnh chuyên sâu (chụp X-quang, cắt lớp vi tính CT, cộng hưởng từ MRI, siêu âm) và báo cáo kết luận của bác sĩ chẩn đoán hình ảnh.",
  organizations: "Bảng danh mục các bệnh viện, trung tâm y tế, phòng khám đa khoa, chuỗi cơ sở chăm sóc sức khỏe và đơn vị vận hành y tế trong hệ thống.",
  payers: "Bảng danh mục các công ty bảo hiểm y tế, quỹ bảo trợ xã hội và cơ quan quản lý chi trả viện phí chính thức.",
  payer_transitions: "Bảng lịch sử chuyển đổi gói bảo hiểm hoặc chuyển quyền bảo trợ chi trả viện phí của bệnh nhân giữa các giai đoạn.",
  providers: "Bảng danh bạ y bác sĩ, điều dưỡng, chuyên viên chăm sóc sức khỏe và nhân viên y tế phụ trách thăm khám, chỉ định điều trị.",
  supplies: "Bảng quản lý vật tư y tế tiêu hao, thiết bị hỗ trợ và dụng cụ dùng trong quá trình khám chữa bệnh tại cơ sở y tế."
};

export const INITIAL_TABLES = {
  orders: {
    table_name: 'orders',
    database_name: 'ecommerce_db',
    schema_name: 'public',
    service_type: 'PostgreSQL',
    fully_qualified_name: 'postgres.ecommerce_db.public.orders',
    description: 'Bảng lưu trữ thông tin đơn hàng của khách hàng trên sàn thương mại điện tử',
    row_count: 15420,
    column_count: 7,
    size_mb: '4.8 MB',
    freshness: '15 phút trước',
    version: 'v1.2',
    followers: 18,
    is_following: false,
    tier: 'Tier.Tier1',
    tier_label: 'Tier 1 - Mission Critical',
    owner: { name: 'Data Engineering Ops', avatar: '👨‍💻', team: 'Data Platform' },
    domain: 'E-Commerce & Retail',
    tags: [
      { name: 'Tier.Tier1', category: 'Tier', color: '#8B5CF6' },
      { name: 'PII.Sensitive', category: 'PII', color: '#EC4899' },
      { name: 'Finance.Confidential', category: 'Governance', color: '#F59E0B' },
      { name: 'Gold_Certified', category: 'Quality', color: '#10B981' }
    ],

    version_history: [
      { version: 'v1.2', date: '2026-10-01 14:30', author: 'Alex Nguyen', changes: ['Thêm ràng buộc DQ Rule: total_amount Between', 'Nâng cấp Tier lên Tier 1'] },
      { version: 'v1.1', date: '2026-09-25 09:15', author: 'Linh Tran', changes: ['Bổ sung mô tả cho các cột delivered_at, paid_at', 'Gắn nhãn PII.Sensitive'] },
      { version: 'v1.0', date: '2026-09-10 08:00', author: 'System Ingestion', changes: ['Khởi tạo bảng lần đầu từ Postgres Ingestion'] }
    ],

    columns: [
      { 
        name: 'order_id', 
        type: 'VARCHAR(64)', 
        nullable: false, 
        is_pk: true,
        null_pct: 0.0, 
        distinct: 15420, 
        distinct_pct: 100.0,
        description: 'Mã định danh duy nhất của đơn hàng (Primary Key)',
        tags: ['PII.NonSensitive', 'Identifier'],
        stats: { min: null, max: null, mean: null, stddev: null },
        frequently_joined: ['fact_orders_daily.order_id', 'order_items.order_id']
      },
      { 
        name: 'customer_id', 
        type: 'VARCHAR(64)', 
        nullable: true, 
        null_pct: 0.1, 
        distinct: 3210, 
        distinct_pct: 20.8,
        description: 'Khóa ngoại liên kết hồ sơ khách hàng',
        tags: ['PII.NonSensitive', 'Foreign Key'],
        stats: { min: null, max: null, mean: null },
        frequently_joined: ['customers.customer_id']
      },
      { 
        name: 'total_amount', 
        type: 'NUMERIC(14,2)', 
        nullable: false, 
        null_pct: 0.0, 
        distinct: 8450, 
        distinct_pct: 54.8,
        description: 'Tổng giá trị thanh toán của đơn hàng sau giảm giá (VNĐ)',
        tags: ['Finance.FinancialMetric'],
        stats: { min: '10,000 đ', max: '48,500,000 đ', mean: '1,420,000 đ', stddev: '850,000 đ' },
        histogram: [
          { bucket: '10k - 500k', pct: 45, count: 6939 },
          { bucket: '500k - 2M', pct: 32, count: 4934 },
          { bucket: '2M - 10M', pct: 18, count: 2775 },
          { bucket: '10M - 50M', pct: 5, count: 772 }
        ]
      },
      { 
        name: 'order_status', 
        type: 'VARCHAR(20)', 
        nullable: false, 
        null_pct: 0.0, 
        distinct: 5, 
        distinct_pct: 0.03,
        description: 'Trạng thái xử lý của đơn hàng',
        tags: ['Enum', 'Status'],
        stats: { sample_values: ['PENDING', 'PROCESSING', 'SHIPPED', 'COMPLETED', 'CANCELLED'] },
        histogram: [
          { bucket: 'COMPLETED', pct: 62, count: 9560 },
          { bucket: 'SHIPPED', pct: 18, count: 2775 },
          { bucket: 'PROCESSING', pct: 12, count: 1850 },
          { bucket: 'PENDING', pct: 5, count: 771 },
          { bucket: 'CANCELLED', pct: 3, count: 464 }
        ]
      },
      { 
        name: 'created_at', 
        type: 'TIMESTAMP', 
        nullable: false, 
        null_pct: 0.0, 
        distinct: 15410, 
        distinct_pct: 99.9,
        description: 'Thời điểm khách hàng gửi đơn hàng',
        tags: ['Temporal', 'EventTime'],
        stats: { min: '2026-01-01 00:00', max: '2026-09-30 09:30' }
      },
      { 
        name: 'delivered_at', 
        type: 'TIMESTAMP', 
        nullable: true, 
        null_pct: 12.0, 
        distinct: 13200, 
        distinct_pct: 85.6,
        description: 'Thời điểm kiện hàng giao thành công',
        tags: ['Temporal', 'Fulfillment'],
        stats: { min: '2026-01-01 14:20', max: '2026-09-30 10:00' }
      },
      { 
        name: 'paid_at', 
        type: 'TIMESTAMP', 
        nullable: true, 
        null_pct: 5.96, 
        distinct: 14100, 
        distinct_pct: 91.4,
        description: 'Thời điểm cổng thanh toán xác nhận giao dịch',
        tags: ['Temporal', 'Payment'],
        stats: { min: '2026-01-01 00:05', max: '2026-09-30 09:45' }
      }
    ],

    // OBSERVABILITY SUITE
    observability: {
      health_score: 94.8,
      health_status: 'HEALTHY',
      freshness: {
        sla_target: '30 phút',
        actual_delay: '15 phút trước',
        status: 'HEALTHY',
        last_sync: '2026-10-02 09:32:15 UTC'
      },
      volume: {
        current_rows: 15420,
        expected_range: '14,800 - 16,000',
        anomaly_detected: false,
        daily_delta: '+3.4%',
        trend_status: 'NORMAL'
      },
      test_suites: {
        total_tests: 14,
        passed: 13,
        warning: 1,
        failed: 0,
        pass_rate: '92.8%'
      },
      dimensions: [
        { name: 'Tính đầy đủ (Completeness)', score: 96, status: 'GOOD' },
        { name: 'Tính duy nhất (Uniqueness)', score: 100, status: 'EXCELLENT' },
        { name: 'Tính hợp lệ (Validity)', score: 98, status: 'EXCELLENT' },
        { name: 'Tính kịp thời (Timeliness)', score: 99, status: 'EXCELLENT' },
        { name: 'Tính nhất quán (Consistency)', score: 88, status: 'WARNING' }
      ],
      recent_runs: [
        { date: '26/09', passed: 14, failed: 0, warning: 0 },
        { date: '27/09', passed: 14, failed: 0, warning: 0 },
        { date: '28/09', passed: 14, failed: 0, warning: 0 },
        { date: '29/09', passed: 13, failed: 0, warning: 1 },
        { date: '30/09', passed: 13, failed: 0, warning: 1 },
        { date: '01/10', passed: 14, failed: 0, warning: 0 },
        { date: 'Hôm nay', passed: 13, failed: 0, warning: 1 }
      ],
      alert_channels: [
        { type: 'Slack', channel: '#data-alerts-ecommerce', status: 'ACTIVE' },
        { type: 'Microsoft Teams', channel: 'Data Engineering Incident Room', status: 'ACTIVE' },
        { type: 'PagerDuty', service: 'High Priority DataOps On-Call', status: 'STANDBY' }
      ],
      incidents: [
        {
          id: 'INC-2026-089',
          title: 'Phát hiện 3 đơn COMPLETED nhưng thiếu paid_at',
          severity: 'MEDIUM',
          status: 'INVESTIGATING',
          detected_at: '2 giờ trước',
          assigned_to: 'Alex Nguyen (DataOps)'
        }
      ]
    },

    // LINEAGE & IMPACT ANALYSIS
    lineage: {
      upstream: [
        {
          id: 'src_pos',
          name: 'pos_cashier_events',
          service: 'Kafka Stream',
          type: 'topic',
          fqn: 'kafka.prod_cluster.pos_cashier_events',
          health: 'HEALTHY'
        },
        {
          id: 'src_stripe',
          name: 'stripe_payment_intents',
          service: 'API Webhook',
          type: 'api',
          fqn: 'stripe.webhooks.payment_intents',
          health: 'HEALTHY'
        }
      ],
      pipelines: [
        {
          id: 'pipe_airflow',
          name: 'airflow.sync_orders_hourly',
          engine: 'Apache Airflow',
          type: 'pipeline',
          status: 'SUCCESS',
          last_run: '15 phút trước'
        },
        {
          id: 'pipe_dbt',
          name: 'dbt.stg_ecommerce_orders',
          engine: 'dbt Core',
          type: 'pipeline',
          status: 'SUCCESS',
          last_run: '12 phút trước'
        }
      ],
      current: {
        id: 'table_orders',
        name: 'orders',
        fqn: 'postgres.ecommerce_db.public.orders',
        tier: 'Tier.Tier1',
        type: 'table',
        health: 'HEALTHY'
      },
      downstream: [
        {
          id: 'down_fact',
          name: 'analytics.fact_orders_daily',
          service: 'Snowflake DW',
          type: 'table',
          fqn: 'snowflake.analytics.fact_orders_daily',
          tier: 'Tier.Tier1',
          health: 'HEALTHY',
          owner: 'BI Team'
        },
        {
          id: 'down_churn',
          name: 'ml_models.customer_churn_feature_store',
          service: 'Databricks',
          type: 'table',
          fqn: 'databricks.feature_store.customer_churn',
          tier: 'Tier.Tier2',
          health: 'HEALTHY',
          owner: 'MLOps'
        },
        {
          id: 'down_tableau',
          name: 'Executive Daily Revenue Dashboard',
          service: 'Tableau Server',
          type: 'dashboard',
          fqn: 'tableau.finance.revenue_executive_board',
          tier: 'Tier.Tier1',
          health: 'ACTIVE',
          owner: 'Finance Director'
        },
        {
          id: 'down_looker',
          name: 'Order Fulfillment & SLA Tracker',
          service: 'Looker',
          type: 'dashboard',
          fqn: 'looker.operations.fulfillment_sla',
          tier: 'Tier.Tier2',
          health: 'ACTIVE',
          owner: 'Operations Team'
        }
      ]
    },

    // ACTIVITY FEED & TASKS (COLLABORATION)
    activity_feed: [
      {
        id: 'act-01',
        type: 'conversation',
        author: 'Alex Nguyen',
        avatar: '👨‍💻',
        time: '30 phút trước',
        content: 'Đã kích hoạt bộ kiểm thử DQ Rule `total_amount Between` từ Recommender, dữ liệu doanh thu tháng này rất ổn định.'
      },
      {
        id: 'act-02',
        type: 'task',
        author: 'Linh Tran',
        avatar: '👩‍💼',
        time: '2 giờ trước',
        title: 'Yêu cầu cập nhật mô tả cột `delivered_at`',
        status: 'OPEN',
        assignee: 'DataOps Team'
      },
      {
        id: 'act-03',
        type: 'announcement',
        author: 'Chief Data Officer',
        avatar: '📢',
        time: '1 ngày trước',
        title: 'Thông báo: Bảng `orders` đã chính thức được nâng hạng lên Tier.Tier1 (Mission Critical).'
      }
    ],

    // SAMPLE ROWS (WITH MASKABLE FIELDS)
    sample_data: [
      { order_id: 'ORD-99201', customer_id: 'CUST-8812', total_amount: '1,250,000 đ', order_status: 'COMPLETED', created_at: '2026-09-30 08:15:20', delivered_at: '2026-09-30 11:30:00', paid_at: '2026-09-30 08:16:05' },
      { order_id: 'ORD-99202', customer_id: 'CUST-3419', total_amount: '450,000 đ', order_status: 'SHIPPED', created_at: '2026-09-30 08:30:11', delivered_at: null, paid_at: '2026-09-30 08:31:00' },
      { order_id: 'ORD-99203', customer_id: 'CUST-5510', total_amount: '5,800,000 đ', order_status: 'PROCESSING', created_at: '2026-09-30 08:45:00', delivered_at: null, paid_at: '2026-09-30 08:45:30' },
      { order_id: 'ORD-99204', customer_id: 'CUST-9014', total_amount: '180,000 đ', order_status: 'PENDING', created_at: '2026-09-30 09:10:00', delivered_at: null, paid_at: null },
      { order_id: 'ORD-99205', customer_id: 'CUST-1120', total_amount: '12,900,000 đ', order_status: 'COMPLETED', created_at: '2026-09-30 09:25:40', delivered_at: '2026-09-30 14:10:00', paid_at: '2026-09-30 09:26:15' }
    ]
  },

  patients: {
    table_name: 'patients',
    database_name: 'HealthCare',
    schema_name: 'public',
    service_type: 'PostgreSQL',
    fully_qualified_name: 'healthcare_postgres.HealthCare.public.patients',
    description: 'Bảng hồ sơ định danh và thông tin lâm sàng bệnh nhân tích hợp trực tiếp từ OpenMetadata',
    row_count: 108,
    column_count: 28,
    size_mb: '0.4 MB',
    freshness: '10 phút trước',
    version: 'v1.4',
    followers: 24,
    is_following: false,
    tier: 'Tier.Tier1',
    tier_label: 'Tier 1 - Mission Critical',
    owner: { name: 'Dr. Jane Foster (Clinical Data Steward)', avatar: '👩‍⚕️', team: 'Healthcare Informatics' },
    domain: 'Healthcare & Life Sciences',
    tags: [
      { name: 'Tier.Tier1', category: 'Tier', color: '#8B5CF6' },
      { name: 'PII.Sensitive', category: 'PII', color: '#EC4899' },
      { name: 'HIPAA.Protected', category: 'Compliance', color: '#EF4444' },
      { name: 'Clinical_Core', category: 'Governance', color: '#10B981' }
    ],

    version_history: [
      { version: 'v1.4', date: '2026-10-02 09:30', author: 'OpenMetadata Profiler', changes: ['Cập nhật metrics profiling từ OpenMetadata live instance', 'Kiểm tra 28 cột dữ liệu'] },
      { version: 'v1.3', date: '2026-09-29 11:20', author: 'Dr. Jane Foster', changes: ['Thêm ràng buộc DQ Rule: birthdate <= deathdate', 'Gắn nhãn HIPAA Protected'] },
      { version: 'v1.0', date: '2026-09-15 08:00', author: 'PostgreSQL Ingestion', changes: ['Đồng bộ dữ liệu ban đầu từ healthcare_postgres service'] }
    ],

    columns: [
      {
        name: 'id',
        type: 'UUID',
        nullable: false,
        is_pk: true,
        null_pct: 0.0,
        distinct: 108,
        distinct_pct: 100.0,
        description: 'Mã định danh bệnh nhân duy nhất (Universal Patient Identifier)',
        tags: ['Identifier', 'PII.Sensitive'],
        stats: { min: '00bcbfc6-c7b9-bd0e-3d95-071f9fba6321', max: 'fd0d7b3a-307d-07b8-9d7e-2424e1feb9e4', sample_values: ['00bcbfc6-c7b9-bd0e-3d95-071f9fba6321', 'fd0d7b3a-307d-07b8-9d7e-2424e1feb9e4'] },
        histogram: [
          { label: '0x00-0x3F', count: 28, pct: 26 },
          { label: '0x40-0x7F', count: 26, pct: 24 },
          { label: '0x80-0xBF', count: 27, pct: 25 },
          { label: '0xC0-0xFF', count: 27, pct: 25 }
        ]
      },
      {
        name: 'birthdate',
        type: 'DATE',
        nullable: false,
        is_pk: false,
        null_pct: 0.0,
        distinct: 97,
        distinct_pct: 89.8,
        description: 'Ngày tháng năm sinh của bệnh nhân',
        tags: ['PII.Sensitive', 'Demographics'],
        stats: { min: '1930-11-06', max: '2026-05-27', sample_values: ['1930-11-06', '1982-04-15', '2026-05-27'] },
        histogram: [
          { label: '< 1960', count: 24, pct: 22 },
          { label: '1960-1980', count: 35, pct: 32 },
          { label: '1980-2000', count: 32, pct: 30 },
          { label: '> 2000', count: 17, pct: 16 }
        ]
      },
      {
        name: 'deathdate',
        type: 'DATE',
        nullable: true,
        is_pk: false,
        null_pct: 91.7,
        distinct: 9,
        distinct_pct: 8.3,
        description: 'Ngày tử vong (để trống nếu bệnh nhân còn sống)',
        tags: ['Clinical', 'Mortality'],
        stats: { min: '1961-08-23', max: '2026-05-03', sample_values: ['1961-08-23', '2021-04-19', '2026-05-03'] },
        histogram: [
          { label: 'Còn sống (NULL)', count: 99, pct: 91.7 },
          { label: 'Đã mất (Có ngày)', count: 9, pct: 8.3 }
        ]
      },
      {
        name: 'ssn',
        type: 'VARCHAR(11)',
        nullable: false,
        is_pk: false,
        null_pct: 0.0,
        distinct: 108,
        distinct_pct: 100.0,
        description: 'Số an sinh xã hội bảo mật (National Social Security Number)',
        tags: ['PII.Sensitive', 'National_ID'],
        stats: { min: '999-01-1001', max: '999-99-9999', sample_values: ['999-12-3456', '999-34-7890', '999-88-9921'] },
        histogram: [
          { label: 'Đạt chuẩn 9 chữ số', count: 108, pct: 100 }
        ]
      },
      {
        name: 'first',
        type: 'VARCHAR(64)',
        nullable: false,
        is_pk: false,
        null_pct: 0.0,
        distinct: 85,
        distinct_pct: 78.7,
        description: 'Tên đệm và tên gọi của bệnh nhân',
        tags: ['PII.Sensitive', 'Name'],
        stats: { min: 'Aaron', max: 'Zoe', sample_values: ['Carlos', 'Elena', 'Arthur'] },
        histogram: [
          { label: 'A-G', count: 32, pct: 30 },
          { label: 'H-N', count: 38, pct: 35 },
          { label: 'O-T', count: 22, pct: 20 },
          { label: 'U-Z', count: 16, pct: 15 }
        ]
      },
      {
        name: 'last',
        type: 'VARCHAR(64)',
        nullable: false,
        is_pk: false,
        null_pct: 0.0,
        distinct: 92,
        distinct_pct: 85.2,
        description: 'Họ của bệnh nhân',
        tags: ['PII.Sensitive', 'Name'],
        stats: { min: 'Adams', max: 'Young', sample_values: ['Morales', 'Rostova', 'Pendleton'] },
        histogram: [
          { label: 'A-G', count: 35, pct: 32 },
          { label: 'H-N', count: 34, pct: 31 },
          { label: 'O-T', count: 24, pct: 22 },
          { label: 'U-Z', count: 15, pct: 15 }
        ]
      },
      {
        name: 'gender',
        type: 'VARCHAR(1)',
        nullable: false,
        is_pk: false,
        null_pct: 0.0,
        distinct: 2,
        distinct_pct: 1.85,
        description: 'Giới tính sinh học (M: Nam, F: Nữ)',
        tags: ['Demographics', 'Gender'],
        stats: { min: 'F', max: 'M', sample_values: ['M', 'F'] },
        histogram: [
          { label: 'F (Nữ)', count: 56, pct: 51.9 },
          { label: 'M (Nam)', count: 52, pct: 48.1 }
        ]
      },
      {
        name: 'healthcare_expenses',
        type: 'NUMERIC(12,2)',
        nullable: false,
        is_pk: false,
        null_pct: 0.0,
        distinct: 108,
        distinct_pct: 100.0,
        description: 'Tổng chi phí khám chữa bệnh tích lũy (USD)',
        tags: ['Finance', 'Claims'],
        stats: { min: 1450.50, max: 185420.00, sample_values: ['15420.50', '64120.00', '185420.00'] },
        histogram: [
          { label: '< $10,000', count: 42, pct: 39 },
          { label: '$10k-$50k', count: 46, pct: 43 },
          { label: '$50k-$100k', count: 14, pct: 13 },
          { label: '> $100k', count: 6, pct: 5 }
        ]
      }
    ],

    lineage: {
      upstream: [
        {
          id: 'src_postgres',
          name: 'healthcare_postgres',
          service: 'PostgreSQL DW',
          type: 'table',
          fqn: 'healthcare_postgres.HealthCare.public.patients',
          health: 'HEALTHY'
        },
        {
          id: 'src_fhir',
          name: 'fhir_clinical_stream',
          service: 'Kafka Stream',
          type: 'topic',
          fqn: 'kafka.prod.fhir_patient_events',
          health: 'HEALTHY'
        },
        {
          id: 'src_emr',
          name: 'hospital_emr_api',
          service: 'API Webhook',
          type: 'api',
          fqn: 'webhook.hospital_emr.patient_intents',
          health: 'HEALTHY'
        }
      ],
      pipelines: [
        {
          id: 'pipe_airflow',
          name: 'airflow.sync_patients_hourly',
          engine: 'Apache Airflow',
          type: 'pipeline',
          status: 'SUCCESS',
          last_run: '10 phút trước'
        },
        {
          id: 'pipe_dbt',
          name: 'dbt.stg_patient_demographics',
          engine: 'dbt Core',
          type: 'pipeline',
          status: 'SUCCESS',
          last_run: '8 phút trước'
        }
      ],
      current: {
        id: 'table_patients',
        name: 'patients',
        fqn: 'healthcare_postgres.HealthCare.public.patients',
        tier: 'Tier.Tier1',
        type: 'table',
        health: 'HEALTHY'
      },
      downstream: [
        {
          id: 'down_fact',
          name: 'analytics.fact_patient_encounters_daily',
          service: 'Snowflake DW',
          type: 'table',
          fqn: 'snowflake.analytics.fact_patient_encounters_daily',
          tier: 'Tier.Tier1',
          health: 'HEALTHY',
          owner: 'Clinical BI Team'
        },
        {
          id: 'down_ml',
          name: 'ml_models.readmission_risk_score',
          service: 'Databricks',
          type: 'table',
          fqn: 'databricks.clinical_ml.readmission_risk_score',
          tier: 'Tier.Tier2',
          health: 'HEALTHY',
          owner: 'Clinical AI Team'
        },
        {
          id: 'down_bi',
          name: 'Executive Clinical Quality Dashboard',
          service: 'Tableau BI',
          type: 'dashboard',
          fqn: 'tableau.dashboards.executive_clinical_summary',
          tier: 'Tier.Tier1',
          health: 'HEALTHY',
          owner: 'Chief Medical Officer'
        }
      ]
    },

    observability: {
      health_score: 97.2,
      health_status: 'HEALTHY',
      freshness: {
        last_updated: '10 phút trước',
        sla_target: '< 30 phút',
        status: 'MEETS_SLA',
        last_sync_timestamp: '2026-10-02 09:30:15 UTC'
      },
      volume: {
        current_rows: 108,
        expected_range: '100 - 120 (+3.2%)',
        growth_rate: '+3.2%',
        anomaly_detected: false,
        anomaly_message: 'Dung lượng bệnh nhân tăng trưởng ổn định từ OpenMetadata Profiler'
      },
      test_suites: {
        passed: 14,
        total: 14,
        score_pct: 100.0,
        critical_failures: 0,
        warnings: 0
      },
      schema_drift: {
        status: 'NO_DRIFT',
        changes_count_30d: 0,
        last_modified: 'Không thay đổi trong 30 ngày qua',
        drift_description: '28 cột khớp 100% định nghĩa OpenMetadata Catalog'
      },
      dimensions: [
        { name: 'Tính Đầy Đủ (Completeness)', score: 98.8, status: 'EXCELLENT', description: 'Tỷ lệ dữ liệu không null theo OpenMetadata Profiler' },
        { name: 'Tính Độc Nhất (Uniqueness)', score: 100.0, status: 'EXCELLENT', description: 'Khóa chính id và ssn đạt 100% duy nhất' },
        { name: 'Tính Hợp Lệ (Validity)', score: 97.5, status: 'EXCELLENT', description: 'Định dạng ngày sinh và mã giới tính M/F hợp lệ' },
        { name: 'Tính Tươi Mới (Freshness)', score: 98.0, status: 'EXCELLENT', description: 'Pipeline đồng bộ đúng SLA dưới 30 phút' },
        { name: 'Tính Nhất Quán (Consistency)', score: 96.0, status: 'GOOD', description: 'Đồng bộ giữa PostgreSQL và OpenMetadata' }
      ],
      recent_runs: [
        { id: 'run_1', test_name: 'test_patient_id_not_null', status: 'SUCCESS', execution_time: '10 phút trước', duration_ms: 92 },
        { id: 'run_2', test_name: 'test_patient_id_unique', status: 'SUCCESS', execution_time: '10 phút trước', duration_ms: 115 },
        { id: 'run_3', test_name: 'test_birthdate_lte_deathdate', status: 'SUCCESS', execution_time: '10 phút trước', duration_ms: 140 }
      ],
      incidents: []
    },

    activity_feed: [
      {
        id: 'act-pat-1',
        type: 'conversation',
        author: 'Dr. Jane Foster',
        avatar: '👩‍⚕️',
        time: '15 phút trước',
        content: 'Bảng `patients` đã được đồng bộ profiling tự động từ OpenMetadata instance. Tất cả 28 cột dữ liệu y tế đã sẵn sàng để sinh Data Quality Rules.'
      },
      {
        id: 'act-pat-2',
        type: 'task',
        author: 'Security Officer',
        avatar: '🛡️',
        time: '1 giờ trước',
        title: 'Xác nhận nhãn PII.Sensitive cho cột SSN & Birthdate',
        content: 'Yêu cầu kiểm tra mặt nạ PII Masking trên giao diện xem mẫu dữ liệu (Sample Data View).'
      }
    ],

    sample_data: [
      { id: '00bcbfc6-c7b9-bd0e-3d95-071f9fba6321', birthdate: '1982-04-15', deathdate: null, ssn: '999-12-3456', first: 'Carlos', last: 'Morales', gender: 'M', city: 'Boston', state: 'Massachusetts', healthcare_expenses: '$15,420.50' },
      { id: '14f8ab92-91e2-4112-98aa-12bfa512e091', birthdate: '1975-09-22', deathdate: null, ssn: '999-34-7890', first: 'Elena', last: 'Rostova', gender: 'F', city: 'Cambridge', state: 'Massachusetts', healthcare_expenses: '$8,950.00' },
      { id: '28bc1294-fa01-8172-88ba-0912fa8912cb', birthdate: '1952-11-03', deathdate: '2021-04-19', ssn: '999-55-1234', first: 'Arthur', last: 'Pendleton', gender: 'M', city: 'Worcester', state: 'Massachusetts', healthcare_expenses: '$64,120.00' },
      { id: '390a1829-192a-bc91-8721-a9f8291ba819', birthdate: '1990-01-30', deathdate: null, ssn: '999-88-9921', first: 'Maya', last: 'Lin', gender: 'F', city: 'Quincy', state: 'Massachusetts', healthcare_expenses: '$4,310.20' },
      { id: 'fd0d7b3a-307d-07b8-9d7e-2424e1feb9e4', birthdate: '1968-07-14', deathdate: null, ssn: '999-71-4567', first: 'Marcus', last: 'Vance', gender: 'M', city: 'Lowell', state: 'Massachusetts', healthcare_expenses: '$28,640.75' }
    ]
  },

  customers: {
    table_name: 'customers',
    database_name: 'ecommerce_db',
    schema_name: 'public',
    service_type: 'PostgreSQL',
    fully_qualified_name: 'postgres.ecommerce_db.public.customers',
    description: 'Danh sách thông tin định danh và hồ sơ khách hàng đã đăng ký',
    row_count: 8920,
    column_count: 4,
    size_mb: '1.9 MB',
    freshness: '1 giờ trước',
    version: 'v1.1',
    followers: 8,
    is_following: false,
    tier: 'Tier.Tier2',
    tier_label: 'Tier 2 - High Importance',
    owner: { name: 'CRM & Marketing Analytics', avatar: '👩‍💼', team: 'Customer Growth' },
    domain: 'CRM & Loyalty',
    tags: [
      { name: 'Tier.Tier2', category: 'Tier', color: '#3B82F6' },
      { name: 'PII.Sensitive', category: 'PII', color: '#EC4899' },
      { name: 'PersonalData.GDPR', category: 'Compliance', color: '#EF4444' }
    ],

    version_history: [
      { version: 'v1.1', date: '2026-09-28 10:00', author: 'Minh Chau', changes: ['Gắn thẻ PII.Sensitive cho cột email', 'Thêm rule email regex format'] }
    ],

    columns: [
      { 
        name: 'customer_id', 
        type: 'VARCHAR(64)', 
        nullable: false, 
        is_pk: true,
        null_pct: 0.0, 
        distinct: 8920, 
        distinct_pct: 100.0,
        description: 'Mã khách hàng duy nhất (Primary Key)',
        tags: ['PII.NonSensitive', 'Identifier'],
        stats: { min: null, max: null }
      },
      { 
        name: 'email', 
        type: 'VARCHAR(255)', 
        nullable: false, 
        null_pct: 0.0, 
        distinct: 8920, 
        distinct_pct: 100.0,
        description: 'Địa chỉ email liên lạc chính của khách hàng',
        tags: ['PII.Sensitive', 'EmailAddress'],
        stats: { min_length: 8, max_length: 45 }
      },
      { 
        name: 'age', 
        type: 'INTEGER', 
        nullable: true, 
        null_pct: 1.34, 
        distinct: 68, 
        distinct_pct: 0.76,
        description: 'Độ tuổi khách hàng (18 - 85)',
        tags: ['Demographic'],
        stats: { min: 18, max: 85, mean: 34 },
        histogram: [
          { bucket: '18 - 25', pct: 28, count: 2497 },
          { bucket: '26 - 40', pct: 44, count: 3925 },
          { bucket: '41 - 60', pct: 22, count: 1962 },
          { bucket: '60+', pct: 6, count: 536 }
        ]
      },
      { 
        name: 'membership_tier', 
        type: 'VARCHAR(20)', 
        nullable: false, 
        null_pct: 0.0, 
        distinct: 4, 
        distinct_pct: 0.04,
        description: 'Hạng hội viên thân thiết (Loyalty Program)',
        tags: ['Categorical', 'LoyaltyTier'],
        stats: { sample_values: ['STANDARD', 'SILVER', 'GOLD', 'PLATINUM'] },
        histogram: [
          { bucket: 'STANDARD', pct: 55, count: 4906 },
          { bucket: 'SILVER', pct: 25, count: 2230 },
          { bucket: 'GOLD', pct: 15, count: 1338 },
          { bucket: 'PLATINUM', pct: 5, count: 446 }
        ]
      }
    ],

    observability: {
      health_score: 98.2,
      health_status: 'EXCELLENT',
      freshness: {
        sla_target: '2 giờ',
        actual_delay: '1 giờ trước',
        status: 'HEALTHY',
        last_sync: '2026-10-02 08:45:00 UTC'
      },
      volume: {
        current_rows: 8920,
        expected_range: '8,800 - 9,100',
        anomaly_detected: false,
        daily_delta: '+0.8%',
        trend_status: 'NORMAL'
      },
      test_suites: {
        total_tests: 8,
        passed: 8,
        warning: 0,
        failed: 0,
        pass_rate: '100%'
      },
      dimensions: [
        { name: 'Tính đầy đủ (Completeness)', score: 99, status: 'EXCELLENT' },
        { name: 'Tính duy nhất (Uniqueness)', score: 100, status: 'EXCELLENT' },
        { name: 'Tính hợp lệ (Validity)', score: 98, status: 'EXCELLENT' },
        { name: 'Tính kịp thời (Timeliness)', score: 97, status: 'EXCELLENT' },
        { name: 'Tính nhất quán (Consistency)', score: 98, status: 'EXCELLENT' }
      ],
      recent_runs: [
        { date: '26/09', passed: 8, failed: 0, warning: 0 },
        { date: '27/09', passed: 8, failed: 0, warning: 0 },
        { date: '28/09', passed: 8, failed: 0, warning: 0 },
        { date: '29/09', passed: 8, failed: 0, warning: 0 },
        { date: '30/09', passed: 8, failed: 0, warning: 0 },
        { date: '01/10', passed: 8, failed: 0, warning: 0 },
        { date: 'Hôm nay', passed: 8, failed: 0, warning: 0 }
      ],
      alert_channels: [
        { type: 'Slack', channel: '#crm-data-alerts', status: 'ACTIVE' }
      ],
      incidents: []
    },

    lineage: {
      upstream: [
        {
          id: 'src_auth0',
          name: 'auth0_user_directory',
          service: 'SSO Identity Provider',
          type: 'api',
          fqn: 'auth0.tenants.production.users',
          health: 'HEALTHY'
        }
      ],
      pipelines: [
        {
          id: 'pipe_fivetran',
          name: 'fivetran.sync_auth0_customers',
          engine: 'Fivetran ETL',
          type: 'pipeline',
          status: 'SUCCESS',
          last_run: '1 giờ trước'
        }
      ],
      current: {
        id: 'table_customers',
        name: 'customers',
        fqn: 'postgres.ecommerce_db.public.customers',
        tier: 'Tier.Tier2',
        type: 'table',
        health: 'HEALTHY'
      },
      downstream: [
        {
          id: 'down_dim_cust',
          name: 'analytics.dim_customers_360',
          service: 'Snowflake DW',
          type: 'table',
          fqn: 'snowflake.analytics.dim_customers_360',
          tier: 'Tier.Tier2',
          health: 'HEALTHY',
          owner: 'Analytics'
        },
        {
          id: 'down_braze',
          name: 'Braze Marketing Automation Hub',
          service: 'Braze CRM',
          type: 'dashboard',
          fqn: 'braze.segments.loyalty_users',
          tier: 'Tier.Tier3',
          health: 'ACTIVE',
          owner: 'Growth'
        }
      ]
    },

    activity_feed: [
      {
        id: 'act-10',
        type: 'conversation',
        author: 'Linh Tran',
        avatar: '👩‍💼',
        time: '3 giờ trước',
        content: 'Bảng customers đã gắn đầy đủ nhãn GDPR cho cột email.'
      }
    ],

    sample_data: [
      { customer_id: 'CUST-1001', email: 'nguyen.van.a@gmail.com', age: 29, membership_tier: 'GOLD' },
      { customer_id: 'CUST-1002', email: 'le.thi.b@outlook.com', age: 34, membership_tier: 'PLATINUM' },
      { customer_id: 'CUST-1003', email: 'tran.minh.c@yahoo.com', age: 22, membership_tier: 'STANDARD' },
      { customer_id: 'CUST-1004', email: 'hoang.duc.d@company.vn', age: 41, membership_tier: 'SILVER' },
      { customer_id: 'CUST-1005', email: 'pham.thu.e@gmail.com', age: 26, membership_tier: 'GOLD' }
    ]
  }
};

export const INITIAL_RULES = [
  {
    id: 'rule_001',
    rule_type: 'columnValuesToBeNotNull',
    target_columns: ['order_id'],
    parameters: {},
    engine: 'BASIC',
    confidence: 1.0,
    reason: 'Cột đóng vai trò định danh chính (ID), không phát hiện bất kỳ giá trị null nào trong toàn bộ 15.420 dòng.',
    evidence: { null_count: 0, null_percentage: 0.0, total_rows: 15420 },
    validation_status: 'VALID',
    validation_message: null,
    status: 'DRAFT',
    edited_parameters: null
  },
  {
    id: 'rule_002',
    rule_type: 'columnValuesToBeUnique',
    target_columns: ['order_id'],
    parameters: {},
    engine: 'BASIC',
    confidence: 1.0,
    reason: 'Tỷ lệ giá trị duy nhất đạt 100%, phù hợp làm khóa chính hoặc mã đơn hàng duy nhất.',
    evidence: { distinct_count: 15420, total_rows: 15420 },
    validation_status: 'VALID',
    validation_message: null,
    status: 'ACCEPTED',
    edited_parameters: null
  },
  {
    id: 'rule_003',
    rule_type: 'columnValuesToBeBetween',
    target_columns: ['total_amount'],
    parameters: {
      minValue: 0.0,
      maxValue: 50000000.0
    },
    engine: 'BASIC',
    confidence: 0.95,
    reason: 'Tổng tiền đơn hàng không thể âm và ngưỡng tối đa thực tế quan sát được là 48.500.000 VNĐ.',
    evidence: { min_observed: 10000.0, max_observed: 48500000.0, total_rows: 15420 },
    validation_status: 'VALID',
    validation_message: null,
    status: 'EDITED',
    edited_parameters: {
      minValue: 0.0,
      maxValue: 100000000.0
    }
  },
  {
    id: 'rule_004',
    rule_type: 'columnValuesToBeInSet',
    target_columns: ['order_status'],
    parameters: {
      allowedValues: ['PENDING', 'PROCESSING', 'SHIPPED', 'COMPLETED', 'CANCELLED']
    },
    engine: 'BASIC',
    confidence: 0.98,
    reason: 'Cột trạng thái có độ biến thiên thấp (cardinality = 5), toàn bộ dữ liệu chỉ nằm trong tập 5 giá trị chuẩn.',
    evidence: { distinct_count: 5, observed_values: ['PENDING', 'PROCESSING', 'SHIPPED', 'COMPLETED', 'CANCELLED'] },
    validation_status: 'VALID',
    validation_message: null,
    status: 'DRAFT',
    edited_parameters: null
  },
  {
    id: 'rule_005',
    rule_type: 'tableCustomSQLQuery',
    target_columns: ['created_at', 'delivered_at'],
    parameters: {
      sqlExpression: 'delivered_at IS NULL OR delivered_at >= created_at'
    },
    engine: 'ADVANCED',
    confidence: 0.92,
    reason: 'Quy luật thời gian (Temporal Logic): Thời điểm giao hàng (delivered_at) phải luôn diễn ra sau hoặc cùng lúc với thời điểm tạo đơn hàng (created_at).',
    evidence: { sample_violations_count: 0, total_rows: 15420 },
    validation_status: 'VALID',
    validation_message: null,
    status: 'DRAFT',
    edited_parameters: null
  },
  {
    id: 'rule_006',
    rule_type: 'tableCustomSQLQuery',
    target_columns: ['order_status', 'paid_at'],
    parameters: {
      sqlExpression: "order_status != 'COMPLETED' OR paid_at IS NOT NULL"
    },
    engine: 'ADVANCED',
    confidence: 0.88,
    reason: 'Phụ thuộc điều kiện ngữ nghĩa (Conditional Dependency): Nếu đơn hàng ở trạng thái đã hoàn thành (COMPLETED) thì bắt buộc phải có thời gian thanh toán (paid_at).',
    evidence: { sample_violations_count: 0 },
    validation_status: 'WARNING',
    validation_message: 'Phát hiện 3 bản ghi cũ có trạng thái COMPLETED nhưng paid_at bị rỗng trong lịch sử di chuyển dữ liệu.',
    status: 'DRAFT',
    edited_parameters: null
  }
];
