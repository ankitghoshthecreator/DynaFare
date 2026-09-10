package com.dynafare.api.domain;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Booking entity — locks in a price from a Quote and ties to a Trip.
 * Maps to the {@code bookings} table.
 * Part 2: Database Layer.
 */
@Entity
@Table(name = "bookings")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Booking {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "trip_id", nullable = false)
    private Trip trip;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "quote_id")
    private Quote quote;

    /**
     * Price at the time the rider confirmed — never changes after booking.
     */
    @Column(name = "quoted_price", nullable = false, precision = 10, scale = 2)
    private BigDecimal quotedPrice;

    /**
     * Final settled price (may differ due to actual distance driven).
     */
    @Column(name = "final_price", precision = 10, scale = 2)
    private BigDecimal finalPrice;

    @Column(name = "surge_multiplier", nullable = false, precision = 4, scale = 2)
    private BigDecimal surgeMultiplier;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private BookingStatus status;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @PrePersist
    void prePersist() {
        if (createdAt == null) createdAt = OffsetDateTime.now();
        if (status == null) status = BookingStatus.PENDING;
        if (surgeMultiplier == null) surgeMultiplier = BigDecimal.ONE;
    }
}
