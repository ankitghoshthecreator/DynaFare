package com.dynafare.api.service;

import com.dynafare.api.dto.DemandEvent;
import com.dynafare.api.dto.DriverLocationEvent;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class KafkaProducerService {

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;

    private static final String LOCATION_TOPIC = "driver-location-events";
    private static final String DEMAND_TOPIC = "demand-events";

    public void publishLocationEvent(DriverLocationEvent event) {
        try {
            String payload = objectMapper.writeValueAsString(event);
            kafkaTemplate.send(LOCATION_TOPIC, event.getDriverId(), payload);
            log.debug("Published location event for driver {}: {}", event.getDriverId(), payload);
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize DriverLocationEvent", e);
        }
    }

    public void publishDemandEvent(DemandEvent event) {
        try {
            String payload = objectMapper.writeValueAsString(event);
            kafkaTemplate.send(DEMAND_TOPIC, event.getZoneId(), payload);
            log.debug("Published demand event for zone {}: {}", event.getZoneId(), payload);
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize DemandEvent", e);
        }
    }
}
