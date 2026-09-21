package com.dynafare.api.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuoteRequest {

    @NotNull(message = "pickupLat is required")
    @DecimalMin(value = "-90.0", message = "pickupLat must be >= -90")
    @DecimalMax(value = "90.0",  message = "pickupLat must be <= 90")
    private Double pickupLat;

    @NotNull(message = "pickupLon is required")
    @DecimalMin(value = "-180.0", message = "pickupLon must be >= -180")
    @DecimalMax(value = "180.0",  message = "pickupLon must be <= 180")
    private Double pickupLon;

    @NotNull(message = "dropoffLat is required")
    @DecimalMin(value = "-90.0", message = "dropoffLat must be >= -90")
    @DecimalMax(value = "90.0",  message = "dropoffLat must be <= 90")
    private Double dropoffLat;

    @NotNull(message = "dropoffLon is required")
    @DecimalMin(value = "-180.0", message = "dropoffLon must be >= -180")
    @DecimalMax(value = "180.0",  message = "dropoffLon must be <= 180")
    private Double dropoffLon;
}
