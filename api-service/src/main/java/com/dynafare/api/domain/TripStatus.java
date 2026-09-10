package com.dynafare.api.domain;

/**
 * Lifecycle states for a Trip.
 */
public enum TripStatus {
    REQUESTED,      // rider requested, searching for driver
    ACCEPTED,       // driver accepted
    IN_PROGRESS,    // driver picked up rider
    COMPLETED,      // trip finished successfully
    CANCELLED       // cancelled by rider or driver
}
