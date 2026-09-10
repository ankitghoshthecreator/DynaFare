package com.dynafare.api.domain;

import jakarta.persistence.*;
import lombok.*;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * Driver entity — maps to the {@code drivers} table.
 * One-to-one with {@link User}: every Driver is also a User with role DRIVER.
 * Part 2: Database Layer.
 */
@Entity
@Table(name = "drivers")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Driver {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(name = "license_no", nullable = false, unique = true, length = 50)
    private String licenseNo;

    @Column(name = "vehicle_type", nullable = false, length = 50)
    private String vehicleType;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private DriverStatus status;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @PrePersist
    void prePersist() {
        if (createdAt == null) createdAt = OffsetDateTime.now();
        if (status == null) status = DriverStatus.OFFLINE;
        if (vehicleType == null) vehicleType = "SEDAN";
    }
}
