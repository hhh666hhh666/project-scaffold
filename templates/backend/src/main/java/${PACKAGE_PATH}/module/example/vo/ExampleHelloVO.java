package ${PACKAGE}.module.example.vo;

/**
 * 出参 VO：**只给前端它需要的字段**，不要把实体整个吐出去。
 */
public record ExampleHelloVO(String message, boolean fromBackend) {
}
