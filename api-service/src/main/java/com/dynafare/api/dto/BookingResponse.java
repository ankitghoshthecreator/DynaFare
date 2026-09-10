package com.dynafare.api.dto;

import com.dynafare.api.domain.BookingStatus;
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
public class BookingResponse {
    private UUID bookingId;
    private UUID quoteId;
    private UUID tripId;
    private BookingStatus status;
    private BigDecimal amount;
    private OffsetDateTime createdAt;
}
