# Online Boutique 服务拓扑图

```mermaid
graph LR
    FE[Frontend] --> AD[AdService]
    FE --> CS[CartService]
    FE --> CO[CheckoutService]
    FE --> CU[CurrencyService]
    FE --> PC[ProductCatalogService]
    FE --> RC[RecommendationService]
    FE --> SH[ShippingService]
    CS --> RD[Redis]
    CO --> CS
    CO --> CU
    CO --> EM[EmailService]
    CO --> PS[PaymentService]
    CO --> PC
    CO --> SH
    RC --> PC

    style FE fill:#ff9800,color:white
    style RD fill:#f44336,color:white
    style CO fill:#2196f3,color:white
```