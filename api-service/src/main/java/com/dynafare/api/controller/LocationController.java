package com.dynafare.api.controller;

import com.dynafare.api.domain.Driver;
import com.dynafare.api.domain.Role;
import com.dynafare.api.domain.User;
import com.dynafare.api.dto.DriverLocationEvent;
import com.dynafare.api.repository.DriverRepository;
import com.dynafare.api.repository.UserRepository;
import com.dynafare.api.service.KafkaProducerService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/locations")
@RequiredArgsConstructor
public class LocationController {

    private final KafkaProducerService kafkaProducerService;
    private final UserRepository userRepository;
    private final DriverRepository driverRepository;

    @PostMapping("/driver")
    public ResponseEntity<Void> publishDriverLocation(@RequestBody DriverLocationEvent event, Authentication authentication) {
        if (authentication != null && authentication.isAuthenticated()) {
            User user = userRepository.findByEmail(authentication.getName())
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User not found"));

            if (user.getRole() == Role.DRIVER) {
                Driver driver = driverRepository.findByUserId(user.getId())
                        .orElseThrow(() -> new ResponseStatusException(HttpStatus.FORBIDDEN, "Driver profile not found"));
                // Enforce driver ID from authenticated driver
                event.setDriverId(driver.getId().toString());
            } else if (user.getRole() != Role.ADMIN) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Only drivers can publish location updates");
            }
        }

        if (event.getZoneId() == null) {
            event.setZoneId("zone-nyc-1"); // fallback dummy zone
        }
        kafkaProducerService.publishLocationEvent(event);
        return ResponseEntity.ok().build();
    }
}
