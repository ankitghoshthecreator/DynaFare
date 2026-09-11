package com.dynafare.api.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DriverLocationEvent {
    private String driverId;
    private String zoneId;
    private double lat;
    private double lon;
}
