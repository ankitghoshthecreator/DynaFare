package com.dynafare.api.controller;

import com.dynafare.api.dto.DriverLocationEvent;
import com.dynafare.api.service.KafkaProducerService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/locations")
@RequiredArgsConstructor
public class LocationController {

    private final KafkaProducerService kafkaProducerService;

    @PostMapping("/driver")
    public ResponseEntity<Void> publishDriverLocation(@RequestBody DriverLocationEvent event) {
        // In a real app, driverId would be extracted from the JWT token of the authenticated driver.
        // For Part 4, we accept it in the payload.
        if (event.getZoneId() == null) {
            event.setZoneId("zone-nyc-1"); // fallback dummy zone
        }
        kafkaProducerService.publishLocationEvent(event);
        return ResponseEntity.ok().build();
    }
}
