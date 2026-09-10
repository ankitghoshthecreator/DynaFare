package com.dynafare.api.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuoteResponse {
    private UUID quoteId;
    private BigDecimal fare;
    private Double distanceKm;
    private Integer durationMin;
    private OffsetDateTime expiresAt;
}
