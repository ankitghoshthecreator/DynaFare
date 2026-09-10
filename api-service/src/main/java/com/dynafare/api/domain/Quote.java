package com.dynafare.api.domain;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Quote entity — a price/ETA estimate returned before booking.
 * Maps to the {@code quotes} table.
 * Part 2: Database Layer.
 */
@Entity
@Table(name = "quotes")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Quote {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "rider_id", nullable = false)
    private User rider;

    @Column(name = "pickup_lat", nullable = false)
    private double pickupLat;

    @Column(name = "pickup_lon", nullable = false)
    private double pickupLon;

    @Column(name = "dropoff_lat", nullable = false)
    private double dropoffLat;

    @Column(name = "dropoff_lon", nullable = false)
    private double dropoffLon;

    @Column(name = "predicted_price", nullable = false, precision = 10, scale = 2)
    private BigDecimal predictedPrice;

    @Column(name = "predicted_eta", nullable = false, precision = 6, scale = 1)
    private BigDecimal predictedEta;

    @Column(name = "surge_multiplier", nullable = false, precision = 4, scale = 2)
    private BigDecimal surgeMultiplier;

    @Column(precision = 4, scale = 2)
    private BigDecimal confidence;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @PrePersist
    void prePersist() {
        if (createdAt == null) createdAt = OffsetDateTime.now();
        if (surgeMultiplier == null) surgeMultiplier = BigDecimal.ONE;
    }
}
